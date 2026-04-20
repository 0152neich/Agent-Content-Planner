from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import jwt
import requests
from jwt import ExpiredSignatureError, InvalidTokenError

from infra.database.pg import SQLDatabase
from infra.database.pg.schemas import SocialConnection, User
from shared.base import BaseModel
from shared.logging import get_logger, redact_message
from shared.settings import Settings
from shared.settings.models import PostgresSettings

from .social_token_cipher_service import SocialTokenCipherService

logger = get_logger(__name__)

FACEBOOK_PROVIDER = "facebook"
FACEBOOK_AUTH_URL = "https://www.facebook.com/v19.0/dialog/oauth"
FACEBOOK_TOKEN_URL = "https://graph.facebook.com/v19.0/oauth/access_token"
FACEBOOK_ME_URL = "https://graph.facebook.com/v19.0/me"
FACEBOOK_PAGES_URL = "https://graph.facebook.com/v19.0/me/accounts"
_STATE_TOKEN_TYPE = "facebook_oauth_state"


class FacebookConnectionServiceOutput(BaseModel):
    status: bool
    data: dict[str, Any] | list[dict[str, Any]] | None = None
    error: str | None = None
    error_code: str | None = None
    code: int = 200


class FacebookOAuthCallbackInput(BaseModel):
    code: str
    state: str


class FacebookConnectionService(BaseModel):
    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self._settings = Settings()
        self._db = SQLDatabase(config=PostgresSettings())
        self._cipher = SocialTokenCipherService()

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    def _is_configured(self) -> bool:
        auth = self._settings.auth
        return bool(
            auth.facebook_enabled
            and auth.facebook_client_id.strip()
            and auth.facebook_client_secret.strip()
            and auth.facebook_redirect_uri.strip()
        )

    def _encode_state(self, *, user_id: str, return_to: str | None = None) -> str:
        now = self._utc_now()
        exp = int(now.timestamp()) + self._settings.auth.facebook_state_ttl_seconds
        payload = {
            "type": _STATE_TOKEN_TYPE,
            "uid": user_id,
            "nonce": secrets.token_urlsafe(20),
            "iat": int(now.timestamp()),
            "exp": exp,
        }
        if return_to:
            payload["return_to"] = return_to
        return jwt.encode(
            payload,
            self._settings.auth.jwt_secret_key,
            algorithm=self._settings.auth.jwt_algorithm,
        )

    def _decode_state(self, state_token: str) -> dict[str, Any]:
        return jwt.decode(
            state_token,
            self._settings.auth.jwt_secret_key,
            algorithms=[self._settings.auth.jwt_algorithm],
            options={"require": ["type", "uid", "nonce", "exp"]},
        )

    def _exchange_code_for_tokens(self, code: str) -> dict[str, Any]:
        auth = self._settings.auth
        params = {
            "client_id": auth.facebook_client_id,
            "client_secret": auth.facebook_client_secret,
            "redirect_uri": auth.facebook_redirect_uri,
            "code": code,
        }
        try:
            response = requests.get(FACEBOOK_TOKEN_URL, params=params, timeout=20)
        except requests.RequestException as exc:
            raise RuntimeError("Facebook token exchange network error.") from exc

        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.status_code != 200:
            error_payload = body.get("error") if isinstance(body, dict) else None
            message = (
                str(
                    error_payload.get("message")
                    if isinstance(error_payload, dict)
                    else ""
                ).strip()
                or "Facebook token exchange failed."
            )
            raise ValueError(message)

        access_token = str(body.get("access_token") or "").strip()
        if not access_token:
            raise ValueError("Facebook did not return access token.")
        return body

    @staticmethod
    def _safe_json(response: requests.Response) -> dict[str, Any]:
        try:
            payload = response.json()
            if isinstance(payload, dict):
                return payload
        except ValueError:
            pass
        return {}

    @staticmethod
    def _extract_graph_error(payload: dict[str, Any], fallback: str) -> str:
        error = payload.get("error")
        if isinstance(error, dict):
            message = str(error.get("message") or "").strip()
            if message:
                return message
        message = str(payload.get("message") or "").strip()
        return message or fallback

    def _fetch_profile(self, access_token: str) -> dict[str, str | None]:
        params = {
            "fields": "id,name",
            "access_token": access_token,
        }
        try:
            response = requests.get(FACEBOOK_ME_URL, params=params, timeout=20)
        except requests.RequestException as exc:
            raise RuntimeError("Facebook profile request network error.") from exc

        body = self._safe_json(response)
        if response.status_code != 200:
            raise ValueError(
                self._extract_graph_error(body, "Failed to fetch Facebook profile.")
            )
        account_id = str(body.get("id") or "").strip()
        if not account_id:
            raise ValueError("Facebook profile id is missing.")
        display_name = str(body.get("name") or "").strip() or None
        return {"account_id": account_id, "display_name": display_name}

    def _resolve_access_token(
        self, user_id: str
    ) -> tuple[str, SocialConnection] | FacebookConnectionServiceOutput:
        with self._db.get_session() as session:
            rows = self._db.get_social_connections(
                session=session,
                filter={"user_id": user_id, "provider": FACEBOOK_PROVIDER},
                limit=1,
            )
        row = rows[0] if rows else None
        if (
            not row
            or row.revoked_at is not None
            or not row.access_token_encrypted
            or not row.access_token_encrypted.strip()
        ):
            return FacebookConnectionServiceOutput(
                status=False,
                data=None,
                error="Facebook account is not connected.",
                error_code="SOCIAL_NOT_CONNECTED",
                code=400,
            )
        expires_at = row.token_expires_at
        if expires_at is not None:
            now = self._utc_now()
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= now:
                return FacebookConnectionServiceOutput(
                    status=False,
                    data=None,
                    error="Facebook access token has expired. Please reconnect your account.",
                    error_code="SOCIAL_TOKEN_EXPIRED",
                    code=401,
                )
        try:
            access_token = self._cipher.decrypt(row.access_token_encrypted)
        except ValueError as exc:
            if "AUTH__SOCIAL_TOKEN_ENCRYPTION_KEY" in str(exc):
                return FacebookConnectionServiceOutput(
                    status=False,
                    data=None,
                    error="Social token encryption key is not configured.",
                    error_code="SOCIAL_CONFIG_INVALID",
                    code=500,
                )
            return FacebookConnectionServiceOutput(
                status=False,
                data=None,
                error="Invalid stored Facebook credentials. Please reconnect your account.",
                error_code="SOCIAL_TOKEN_INVALID",
                code=401,
            )
        return access_token, row

    def build_connect_url(
        self, user: User, return_to: str | None = None
    ) -> FacebookConnectionServiceOutput:
        if not self._is_configured():
            return FacebookConnectionServiceOutput(
                status=False,
                data=None,
                error="Facebook OAuth is not configured.",
                error_code="SOCIAL_CONFIG_INVALID",
                code=500,
            )
        if not user.id:
            return FacebookConnectionServiceOutput(
                status=False,
                data=None,
                error="Invalid user context.",
                error_code="SOCIAL_INVALID_USER",
                code=400,
            )

        state = self._encode_state(user_id=str(user.id), return_to=return_to)
        query = urlencode(
            {
                "client_id": self._settings.auth.facebook_client_id,
                "redirect_uri": self._settings.auth.facebook_redirect_uri,
                "state": state,
                "response_type": "code",
                "scope": self._settings.auth.facebook_scope.strip(),
            }
        )
        return FacebookConnectionServiceOutput(
            status=True,
            data={"authorize_url": f"{FACEBOOK_AUTH_URL}?{query}"},
            error=None,
            error_code=None,
            code=200,
        )

    def handle_callback(
        self, inputs: FacebookOAuthCallbackInput
    ) -> FacebookConnectionServiceOutput:
        if not self._is_configured():
            return FacebookConnectionServiceOutput(
                status=False,
                data=None,
                error="Facebook OAuth is not configured.",
                error_code="SOCIAL_CONFIG_INVALID",
                code=500,
            )
        try:
            state_payload = self._decode_state(inputs.state)
            if state_payload.get("type") != _STATE_TOKEN_TYPE:
                return FacebookConnectionServiceOutput(
                    status=False,
                    data=None,
                    error="Invalid OAuth state.",
                    error_code="SOCIAL_INVALID_STATE",
                    code=401,
                )
            user_id = str(state_payload.get("uid") or "").strip()
            return_to = str(state_payload.get("return_to") or "").strip() or None
            if not user_id:
                return FacebookConnectionServiceOutput(
                    status=False,
                    data=None,
                    error="Invalid OAuth state.",
                    error_code="SOCIAL_INVALID_STATE",
                    code=401,
                )

            tokens = self._exchange_code_for_tokens(inputs.code)
            access_token = str(tokens.get("access_token") or "").strip()
            expires_at = None
            expires_in_raw = tokens.get("expires_in")
            if expires_in_raw is not None:
                try:
                    expires_at = self._utc_now() + timedelta(
                        seconds=int(expires_in_raw)
                    )
                except (TypeError, ValueError):
                    expires_at = None
            profile = self._fetch_profile(access_token)
            encrypted_access_token = self._cipher.encrypt(access_token)

            with self._db.get_session() as session:
                existing_rows = self._db.get_social_connections(
                    session=session,
                    filter={"user_id": user_id, "provider": FACEBOOK_PROVIDER},
                    limit=1,
                )
                existing = existing_rows[0] if existing_rows else None
                if existing:
                    to_save = SocialConnection(
                        id=existing.id,
                        user_id=existing.user_id,
                        provider=existing.provider,
                        access_token_encrypted=encrypted_access_token,
                        refresh_token_encrypted=None,
                        token_expires_at=expires_at,
                        provider_account_id=profile["account_id"],
                        provider_account_name=profile["display_name"],
                        revoked_at=None,
                    )
                    persisted = self._db.update_social_connection(
                        session=session, model=to_save
                    )
                else:
                    persisted = self._db.insert_social_connection(
                        session=session,
                        model=SocialConnection(
                            user_id=user_id,
                            provider=FACEBOOK_PROVIDER,
                            access_token_encrypted=encrypted_access_token,
                            refresh_token_encrypted=None,
                            token_expires_at=expires_at,
                            provider_account_id=profile["account_id"],
                            provider_account_name=profile["display_name"],
                            revoked_at=None,
                        ),
                    )
            if not persisted:
                return FacebookConnectionServiceOutput(
                    status=False,
                    data=None,
                    error="Failed to persist Facebook connection.",
                    error_code="SOCIAL_PERSIST_FAILED",
                    code=500,
                )
            return FacebookConnectionServiceOutput(
                status=True,
                data={
                    "connected": True,
                    "provider": FACEBOOK_PROVIDER,
                    "display_name": persisted.provider_account_name,
                    "account_id": persisted.provider_account_id,
                    "expires_at": persisted.token_expires_at,
                    "return_to": return_to,
                },
                error=None,
                error_code=None,
                code=200,
            )
        except ExpiredSignatureError:
            return FacebookConnectionServiceOutput(
                status=False,
                data=None,
                error="OAuth state expired.",
                error_code="SOCIAL_STATE_EXPIRED",
                code=401,
            )
        except InvalidTokenError:
            return FacebookConnectionServiceOutput(
                status=False,
                data=None,
                error="Invalid OAuth state.",
                error_code="SOCIAL_INVALID_STATE",
                code=401,
            )
        except ValueError as exc:
            if "AUTH__SOCIAL_TOKEN_ENCRYPTION_KEY" in str(exc):
                return FacebookConnectionServiceOutput(
                    status=False,
                    data=None,
                    error="Social token encryption key is not configured.",
                    error_code="SOCIAL_CONFIG_INVALID",
                    code=500,
                )
            logger.warning(
                "facebook_oauth_callback_failed", error=redact_message(str(exc))
            )
            return FacebookConnectionServiceOutput(
                status=False,
                data=None,
                error=redact_message(str(exc)),
                error_code="SOCIAL_OAUTH_FAILED",
                code=400,
            )
        except Exception as exc:
            logger.exception(
                "facebook_oauth_callback_unexpected", error=redact_message(str(exc))
            )
            return FacebookConnectionServiceOutput(
                status=False,
                data=None,
                error="Unexpected error while connecting Facebook.",
                error_code="SOCIAL_UNEXPECTED_ERROR",
                code=500,
            )

    def get_connection(self, user: User) -> FacebookConnectionServiceOutput:
        if not user.id:
            return FacebookConnectionServiceOutput(
                status=False,
                data=None,
                error="Invalid user context.",
                error_code="SOCIAL_INVALID_USER",
                code=400,
            )
        with self._db.get_session() as session:
            rows = self._db.get_social_connections(
                session=session,
                filter={"user_id": str(user.id), "provider": FACEBOOK_PROVIDER},
                limit=1,
            )
        row = rows[0] if rows else None
        expires_at = row.token_expires_at if row else None
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        connected = bool(
            row
            and row.revoked_at is None
            and row.access_token_encrypted.strip()
            and (expires_at is None or expires_at > self._utc_now())
        )
        return FacebookConnectionServiceOutput(
            status=True,
            data={
                "connected": connected,
                "provider": FACEBOOK_PROVIDER,
                "display_name": row.provider_account_name if row else None,
                "account_id": row.provider_account_id if row else None,
                "expires_at": expires_at,
            },
            error=None,
            error_code=None,
            code=200,
        )

    def list_pages(self, user: User) -> FacebookConnectionServiceOutput:
        if not user.id:
            return FacebookConnectionServiceOutput(
                status=False,
                data=None,
                error="Invalid user context.",
                error_code="SOCIAL_INVALID_USER",
                code=400,
            )
        credentials = self._resolve_access_token(str(user.id))
        if isinstance(credentials, FacebookConnectionServiceOutput):
            return credentials
        access_token, _ = credentials
        params = {
            "fields": "id,name,tasks,access_token",
            "access_token": access_token,
        }
        try:
            response = requests.get(FACEBOOK_PAGES_URL, params=params, timeout=20)
        except requests.RequestException as exc:
            logger.warning(
                "facebook_list_pages_network_error", error=redact_message(str(exc))
            )
            return FacebookConnectionServiceOutput(
                status=False,
                data=None,
                error="Unable to reach Facebook API. Please try again.",
                error_code="SOCIAL_PROVIDER_NETWORK_ERROR",
                code=400,
            )
        payload = self._safe_json(response)
        if response.status_code != 200:
            return FacebookConnectionServiceOutput(
                status=False,
                data=None,
                error=self._extract_graph_error(
                    payload, "Failed to fetch Facebook pages."
                ),
                error_code="SOCIAL_PROVIDER_ERROR",
                code=400,
            )

        data = payload.get("data")
        if not isinstance(data, list):
            return FacebookConnectionServiceOutput(
                status=True,
                data=[],
                error=None,
                error_code=None,
                code=200,
            )
        filtered: list[dict[str, Any]] = []
        for page in data:
            if not isinstance(page, dict):
                continue
            filtered.append(
                {
                    "id": str(page.get("id") or "").strip(),
                    "name": str(page.get("name") or "").strip(),
                    "tasks": [
                        str(task).strip()
                        for task in page.get("tasks", [])
                        if str(task).strip()
                    ]
                    if isinstance(page.get("tasks"), list)
                    else [],
                    "perms": [
                        str(perm).strip()
                        for perm in page.get("perms", [])
                        if str(perm).strip()
                    ]
                    if isinstance(page.get("perms"), list)
                    else [],
                }
            )

        return FacebookConnectionServiceOutput(
            status=True,
            data=filtered,
            error=None,
            error_code=None,
            code=200,
        )

    def disconnect(self, user: User) -> FacebookConnectionServiceOutput:
        if not user.id:
            return FacebookConnectionServiceOutput(
                status=False,
                data=None,
                error="Invalid user context.",
                error_code="SOCIAL_INVALID_USER",
                code=400,
            )
        with self._db.get_session() as session:
            rows = self._db.get_social_connections(
                session=session,
                filter={"user_id": str(user.id), "provider": FACEBOOK_PROVIDER},
                limit=1,
            )
            row = rows[0] if rows else None
            if not row:
                return FacebookConnectionServiceOutput(
                    status=True,
                    data={"disconnected": True},
                    error=None,
                    error_code=None,
                    code=200,
                )
            payload = SocialConnection(
                id=row.id,
                user_id=row.user_id,
                provider=row.provider,
                access_token_encrypted=row.access_token_encrypted,
                refresh_token_encrypted=row.refresh_token_encrypted,
                token_expires_at=None,
                provider_account_id=row.provider_account_id,
                provider_account_name=row.provider_account_name,
                revoked_at=self._utc_now(),
            )
            self._db.update_social_connection(session=session, model=payload)
        return FacebookConnectionServiceOutput(
            status=True,
            data={"disconnected": True},
            error=None,
            error_code=None,
            code=200,
        )
