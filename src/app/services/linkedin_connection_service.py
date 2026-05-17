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

LINKEDIN_PROVIDER = "linkedin"
LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
LINKEDIN_ME_URL = "https://api.linkedin.com/v2/me"
_STATE_TOKEN_TYPE = "linkedin_oauth_state"


class LinkedInConnectionServiceOutput(BaseModel):
    status: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    error_code: str | None = None
    code: int = 200


class LinkedInOAuthCallbackInput(BaseModel):
    code: str
    state: str


class LinkedInConnectionService(BaseModel):
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
            auth.linkedin_enabled
            and auth.linkedin_client_id.strip()
            and auth.linkedin_client_secret.strip()
            and auth.linkedin_redirect_uri.strip()
        )

    def _encode_state(self, *, user_id: str, return_to: str | None = None) -> str:
        now = self._utc_now()
        exp = int(now.timestamp()) + self._settings.auth.linkedin_state_ttl_seconds
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
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": auth.linkedin_client_id,
            "client_secret": auth.linkedin_client_secret,
            "redirect_uri": auth.linkedin_redirect_uri,
        }
        try:
            response = requests.post(LINKEDIN_TOKEN_URL, data=payload, timeout=20)
        except requests.RequestException as exc:
            raise RuntimeError("LinkedIn token exchange network error.") from exc

        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.status_code != 200:
            message = (
                str(body.get("error_description") or body.get("error") or "").strip()
                or "LinkedIn token exchange failed."
            )
            raise ValueError(message)
        access_token = str(body.get("access_token") or "").strip()
        if not access_token:
            raise ValueError("LinkedIn did not return access token.")
        return body

    def _fetch_linkedin_profile(self, access_token: str) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        # Preferred path for OAuth apps using OIDC scopes (openid/profile/email).
        try:
            response = requests.get(
                LINKEDIN_USERINFO_URL,
                headers=headers,
                timeout=20,
            )
        except requests.RequestException as exc:
            raise RuntimeError("LinkedIn profile request network error.") from exc

        try:
            body = response.json()
        except ValueError:
            body = {}

        if response.status_code == 200 and isinstance(body, dict):
            member_id = str(body.get("sub") or "").strip()
            if member_id:
                display_name = str(body.get("name") or "").strip() or None
                return {
                    "member_id": member_id,
                    "member_urn": f"urn:li:person:{member_id}",
                    "display_name": display_name,
                }

        # Backward-compatible fallback for legacy scopes.
        try:
            legacy_response = requests.get(
                LINKEDIN_ME_URL,
                headers=headers,
                timeout=20,
            )
        except requests.RequestException as exc:
            raise RuntimeError("LinkedIn profile request network error.") from exc

        try:
            legacy_body = legacy_response.json()
        except ValueError:
            legacy_body = {}

        if legacy_response.status_code != 200:
            message = str(legacy_body.get("message") or "").strip()
            if not message and isinstance(body, dict):
                message = str(body.get("message") or "").strip()
            raise ValueError(message or "Failed to fetch LinkedIn profile.")

        member_id = str(legacy_body.get("id") or "").strip()
        if not member_id:
            raise ValueError("LinkedIn profile id is missing.")
        first_name = str(legacy_body.get("localizedFirstName") or "").strip()
        last_name = str(legacy_body.get("localizedLastName") or "").strip()
        full_name = f"{first_name} {last_name}".strip() or None
        return {
            "member_id": member_id,
            "member_urn": f"urn:li:person:{member_id}",
            "display_name": full_name,
        }

    def build_connect_url(
        self, user: User, return_to: str | None = None
    ) -> LinkedInConnectionServiceOutput:
        if not self._is_configured():
            return LinkedInConnectionServiceOutput(
                status=False,
                data=None,
                error="LinkedIn OAuth is not configured.",
                error_code="SOCIAL_CONFIG_INVALID",
                code=500,
            )
        if not user.id:
            return LinkedInConnectionServiceOutput(
                status=False,
                data=None,
                error="Invalid user context.",
                error_code="SOCIAL_INVALID_USER",
                code=400,
            )

        state = self._encode_state(user_id=str(user.id), return_to=return_to)
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self._settings.auth.linkedin_client_id,
                "redirect_uri": self._settings.auth.linkedin_redirect_uri,
                "state": state,
                "scope": self._settings.auth.linkedin_scope.strip(),
            }
        )
        return LinkedInConnectionServiceOutput(
            status=True,
            data={"authorize_url": f"{LINKEDIN_AUTH_URL}?{query}"},
            error=None,
            error_code=None,
            code=200,
        )

    def get_connection(self, user: User) -> LinkedInConnectionServiceOutput:
        if not user.id:
            return LinkedInConnectionServiceOutput(
                status=False,
                data=None,
                error="Invalid user context.",
                error_code="SOCIAL_INVALID_USER",
                code=400,
            )

        with self._db.get_session() as session:
            rows = self._db.get_social_connections(
                session=session,
                filter={"user_id": str(user.id), "provider": LINKEDIN_PROVIDER},
                limit=1,
            )
        row = rows[0] if rows else None
        now = self._utc_now()
        expires_at = row.token_expires_at if row else None
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        connected = bool(
            row
            and row.revoked_at is None
            and row.access_token_encrypted.strip()
            and (expires_at is None or expires_at > now)
        )
        return LinkedInConnectionServiceOutput(
            status=True,
            data={
                "connected": connected,
                "provider": LINKEDIN_PROVIDER,
                "display_name": row.provider_account_name if row else None,
                "member_urn": row.provider_account_id if row else None,
                "expires_at": expires_at,
            },
            error=None,
            error_code=None,
            code=200,
        )

    def handle_callback(
        self, inputs: LinkedInOAuthCallbackInput
    ) -> LinkedInConnectionServiceOutput:
        if not self._is_configured():
            return LinkedInConnectionServiceOutput(
                status=False,
                data=None,
                error="LinkedIn OAuth is not configured.",
                error_code="SOCIAL_CONFIG_INVALID",
                code=500,
            )

        try:
            state_payload = self._decode_state(inputs.state)
            if state_payload.get("type") != _STATE_TOKEN_TYPE:
                return LinkedInConnectionServiceOutput(
                    status=False,
                    data=None,
                    error="Invalid OAuth state.",
                    error_code="SOCIAL_INVALID_STATE",
                    code=401,
                )
            user_id = str(state_payload.get("uid") or "").strip()
            return_to = str(state_payload.get("return_to") or "").strip() or None
            if not user_id:
                return LinkedInConnectionServiceOutput(
                    status=False,
                    data=None,
                    error="Invalid OAuth state.",
                    error_code="SOCIAL_INVALID_STATE",
                    code=401,
                )

            tokens = self._exchange_code_for_tokens(inputs.code)
            access_token = str(tokens.get("access_token") or "").strip()
            refresh_token = str(tokens.get("refresh_token") or "").strip() or None
            expires_in_raw = tokens.get("expires_in")
            expires_at = None
            if expires_in_raw is not None:
                try:
                    expires_at = self._utc_now() + timedelta(
                        seconds=int(expires_in_raw)
                    )
                except (TypeError, ValueError):
                    expires_at = None

            profile = self._fetch_linkedin_profile(access_token)
            encrypted_access_token = self._cipher.encrypt(access_token)
            encrypted_refresh_token = (
                self._cipher.encrypt(refresh_token) if refresh_token else None
            )

            with self._db.get_session() as session:
                existing_rows = self._db.get_social_connections(
                    session=session,
                    filter={"user_id": user_id, "provider": LINKEDIN_PROVIDER},
                    limit=1,
                )
                existing = existing_rows[0] if existing_rows else None
                if existing:
                    to_save = SocialConnection(
                        id=existing.id,
                        user_id=existing.user_id,
                        provider=existing.provider,
                        access_token_encrypted=encrypted_access_token,
                        refresh_token_encrypted=encrypted_refresh_token,
                        token_expires_at=expires_at,
                        provider_account_id=profile["member_urn"],
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
                            provider=LINKEDIN_PROVIDER,
                            access_token_encrypted=encrypted_access_token,
                            refresh_token_encrypted=encrypted_refresh_token,
                            token_expires_at=expires_at,
                            provider_account_id=profile["member_urn"],
                            provider_account_name=profile["display_name"],
                            revoked_at=None,
                        ),
                    )
            if not persisted:
                return LinkedInConnectionServiceOutput(
                    status=False,
                    data=None,
                    error="Failed to persist LinkedIn connection.",
                    error_code="SOCIAL_PERSIST_FAILED",
                    code=500,
                )
            return LinkedInConnectionServiceOutput(
                status=True,
                data={
                    "connected": True,
                    "provider": LINKEDIN_PROVIDER,
                    "display_name": persisted.provider_account_name,
                    "member_urn": persisted.provider_account_id,
                    "expires_at": persisted.token_expires_at,
                    "return_to": return_to,
                },
                error=None,
                error_code=None,
                code=200,
            )
        except ExpiredSignatureError:
            return LinkedInConnectionServiceOutput(
                status=False,
                data=None,
                error="OAuth state expired.",
                error_code="SOCIAL_STATE_EXPIRED",
                code=401,
            )
        except InvalidTokenError:
            return LinkedInConnectionServiceOutput(
                status=False,
                data=None,
                error="Invalid OAuth state.",
                error_code="SOCIAL_INVALID_STATE",
                code=401,
            )
        except ValueError as exc:
            if "AUTH__SOCIAL_TOKEN_ENCRYPTION_KEY" in str(exc):
                return LinkedInConnectionServiceOutput(
                    status=False,
                    data=None,
                    error="Social token encryption key is not configured.",
                    error_code="SOCIAL_CONFIG_INVALID",
                    code=500,
                )
            logger.warning(
                "linkedin_oauth_callback_failed",
                error=redact_message(str(exc)),
            )
            return LinkedInConnectionServiceOutput(
                status=False,
                data=None,
                error=redact_message(str(exc)),
                error_code="SOCIAL_OAUTH_FAILED",
                code=400,
            )
        except Exception as exc:
            logger.exception(
                "linkedin_oauth_callback_unexpected",
                error=redact_message(str(exc)),
            )
            return LinkedInConnectionServiceOutput(
                status=False,
                data=None,
                error="Unexpected error while connecting LinkedIn.",
                error_code="SOCIAL_UNEXPECTED_ERROR",
                code=500,
            )

    def disconnect(self, user: User) -> LinkedInConnectionServiceOutput:
        if not user.id:
            return LinkedInConnectionServiceOutput(
                status=False,
                data=None,
                error="Invalid user context.",
                error_code="SOCIAL_INVALID_USER",
                code=400,
            )
        with self._db.get_session() as session:
            rows = self._db.get_social_connections(
                session=session,
                filter={"user_id": str(user.id), "provider": LINKEDIN_PROVIDER},
                limit=1,
            )
            row = rows[0] if rows else None
            if not row:
                return LinkedInConnectionServiceOutput(
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

        return LinkedInConnectionServiceOutput(
            status=True,
            data={"disconnected": True},
            error=None,
            error_code=None,
            code=200,
        )
