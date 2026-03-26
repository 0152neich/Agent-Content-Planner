from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from infra.database.pg import SQLDatabase
from infra.database.pg.schemas import User, UserIdentity
from shared.base import BaseModel
from shared.logging import get_logger, redact_message
from shared.settings import Settings
from shared.settings.models import PostgresSettings

from .auth_service import AuthService, AuthServiceOutput

logger = get_logger(__name__)

GOOGLE_PROVIDER = "google"
GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
_ALLOWED_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
_STATE_TOKEN_TYPE = "google_oauth_state"


class GoogleAuthError(Exception):
    def __init__(self, message: str, *, code: int = 401) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class GoogleAuthStartOutput(BaseModel):
    status: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    code: int = 200


class GoogleAuthCallbackInput(BaseModel):
    code: str
    state: str
    state_cookie_value: str
    ip: str | None = None
    user_agent: str | None = None


class GoogleAuthService(BaseModel):
    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self._settings = Settings()
        self._db = SQLDatabase(config=PostgresSettings())
        self._auth_service = AuthService()

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _normalize_email(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        return normalized or None

    @staticmethod
    def _truthy_google_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() == "true"
        return False

    def _is_google_enabled(self) -> bool:
        auth = self._settings.auth
        return bool(
            auth.google_enabled
            and auth.google_client_id.strip()
            and auth.google_client_secret.strip()
            and auth.google_redirect_uri.strip()
        )

    def _encode_state_cookie(self, *, state: str, nonce: str) -> str:
        now = self._utc_now()
        exp = int(now.timestamp()) + self._settings.auth.google_state_ttl_seconds
        payload = {
            "type": _STATE_TOKEN_TYPE,
            "state": state,
            "nonce": nonce,
            "iat": int(now.timestamp()),
            "exp": exp,
        }
        return jwt.encode(
            payload,
            self._settings.auth.jwt_secret_key,
            algorithm=self._settings.auth.jwt_algorithm,
        )

    def _decode_state_cookie(self, token: str) -> dict[str, Any]:
        return jwt.decode(
            token,
            self._settings.auth.jwt_secret_key,
            algorithms=[self._settings.auth.jwt_algorithm],
            options={"require": ["type", "state", "nonce", "exp"]},
        )

    def _decode_json_response(self, response_bytes: bytes) -> dict[str, Any]:
        parsed = json.loads(response_bytes.decode("utf-8"))
        if not isinstance(parsed, dict):
            raise GoogleAuthError("Invalid OAuth response payload.", code=401)
        return parsed

    def _post_form(self, url: str, payload: dict[str, str]) -> dict[str, Any]:
        form_body = urlencode(payload).encode("utf-8")
        request = Request(
            url=url,
            data=form_body,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urlopen(request, timeout=15) as response:
                return self._decode_json_response(response.read())
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="ignore")
            logger.warning(
                "google_oauth_http_error", status=exc.code, body=error_body[:500]
            )
            raise GoogleAuthError("Google token exchange failed.", code=401) from exc
        except URLError as exc:
            logger.warning("google_oauth_network_error", error=str(exc))
            raise GoogleAuthError("Google OAuth network error.", code=500) from exc
        except TimeoutError as exc:
            logger.warning("google_oauth_timeout", error=str(exc))
            raise GoogleAuthError("Google OAuth timeout.", code=500) from exc

    def _get_json(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        query = urlencode(params)
        request = Request(url=f"{url}?{query}", method="GET")
        try:
            with urlopen(request, timeout=15) as response:
                return self._decode_json_response(response.read())
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            logger.warning(
                "google_tokeninfo_http_error", status=exc.code, body=body[:500]
            )
            raise GoogleAuthError("Google token validation failed.", code=401) from exc
        except URLError as exc:
            logger.warning("google_tokeninfo_network_error", error=str(exc))
            raise GoogleAuthError(
                "Google token validation network error.", code=500
            ) from exc
        except TimeoutError as exc:
            logger.warning("google_tokeninfo_timeout", error=str(exc))
            raise GoogleAuthError("Google token validation timeout.", code=500) from exc

    def _exchange_code_for_tokens(self, code: str) -> dict[str, Any]:
        auth = self._settings.auth
        payload = {
            "code": code,
            "client_id": auth.google_client_id,
            "client_secret": auth.google_client_secret,
            "redirect_uri": auth.google_redirect_uri,
            "grant_type": "authorization_code",
        }
        tokens = self._post_form(GOOGLE_TOKEN_URL, payload)
        id_token = str(tokens.get("id_token", "")).strip()
        if not id_token:
            raise GoogleAuthError("Google did not return id_token.", code=401)
        return tokens

    def _verify_id_token(self, *, id_token: str, expected_nonce: str) -> dict[str, Any]:
        claims = self._get_json(GOOGLE_TOKENINFO_URL, {"id_token": id_token})
        aud = str(claims.get("aud", "")).strip()
        iss = str(claims.get("iss", "")).strip()
        nonce = str(claims.get("nonce", "")).strip()
        sub = str(claims.get("sub", "")).strip()
        email = self._normalize_email(claims.get("email"))

        if aud != self._settings.auth.google_client_id:
            raise GoogleAuthError("Invalid Google token audience.", code=401)
        if iss not in _ALLOWED_ISSUERS:
            raise GoogleAuthError("Invalid Google token issuer.", code=401)
        if nonce != expected_nonce:
            raise GoogleAuthError("Invalid Google token nonce.", code=401)
        if not sub:
            raise GoogleAuthError("Invalid Google token subject.", code=401)
        if not email:
            raise GoogleAuthError("Google account does not provide email.", code=401)

        exp_raw = claims.get("exp")
        try:
            exp = int(str(exp_raw))
        except Exception as exc:
            raise GoogleAuthError("Invalid Google token expiry.", code=401) from exc
        if exp <= int(self._utc_now().timestamp()):
            raise GoogleAuthError("Google token has expired.", code=401)

        return {
            "sub": sub,
            "email": email,
            "email_verified": self._truthy_google_bool(claims.get("email_verified")),
            "name": str(claims.get("name", "")).strip() or None,
            "picture": str(claims.get("picture", "")).strip() or None,
        }

    def _generate_unique_username(self, *, email: str) -> str:
        base = email.split("@", 1)[0].lower()
        base = re.sub(r"[^a-z0-9_]+", "_", base).strip("_")
        if not base:
            base = "google_user"
        base = base[:40]
        candidate = base
        for _ in range(50):
            with self._db.get_session() as session:
                existing = self._db.get_users(
                    session=session,
                    filter={"user_name": candidate},
                    limit=1,
                )
            if not existing:
                return candidate
            suffix = secrets.token_hex(3)
            candidate = f"{base[:32]}_{suffix}"
        return f"google_{secrets.token_hex(6)}"

    def _upsert_identity_for_user(
        self,
        *,
        user: User,
        provider_sub: str,
        email: str,
        email_verified: bool,
        picture_url: str | None,
    ) -> User:
        with self._db.get_session() as session:
            existing_google_identity = self._db.get_user_identities(
                session=session,
                filter={"user_id": str(user.id), "provider": GOOGLE_PROVIDER},
                limit=1,
            )
            if existing_google_identity:
                identity = existing_google_identity[0]
                if identity.provider_sub != provider_sub:
                    raise GoogleAuthError(
                        "Google account conflict for existing user.",
                        code=409,
                    )
                identity.email = email
                identity.email_verified = email_verified
                identity.picture_url = picture_url
                self._db.update_user_identity(session=session, model=identity)
            else:
                identity = UserIdentity(
                    user_id=str(user.id),
                    provider=GOOGLE_PROVIDER,
                    provider_sub=provider_sub,
                    email=email,
                    email_verified=email_verified,
                    picture_url=picture_url,
                )
                self._db.insert_user_identity(session=session, model=identity)

            updated_user = user
            if (email_verified and not user.email_verified) or (
                picture_url and not user.avatar_url
            ):
                updated_user = User(
                    id=user.id,
                    user_name=user.user_name,
                    email=user.email,
                    password_hash=user.password_hash,
                    full_name=user.full_name,
                    phone=user.phone,
                    avatar_url=picture_url or user.avatar_url,
                    is_active=user.is_active,
                    email_verified=email_verified or user.email_verified,
                    role=user.role,
                )
                persisted = self._db.update_user(session=session, model=updated_user)
                if persisted is not None:
                    updated_user = persisted
            return updated_user

    def build_authorization_request(self) -> GoogleAuthStartOutput:
        if not self._is_google_enabled():
            return GoogleAuthStartOutput(
                status=False,
                data=None,
                error="Google login is not configured.",
                code=500,
            )

        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        state_cookie_value = self._encode_state_cookie(state=state, nonce=nonce)
        query = urlencode(
            {
                "client_id": self._settings.auth.google_client_id,
                "redirect_uri": self._settings.auth.google_redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "nonce": nonce,
                "prompt": "select_account",
            }
        )
        authorize_url = f"{GOOGLE_AUTHORIZE_URL}?{query}"
        return GoogleAuthStartOutput(
            status=True,
            data={
                "authorize_url": authorize_url,
                "state_cookie_value": state_cookie_value,
            },
            error=None,
            code=200,
        )

    def authenticate_with_google(
        self, inputs: GoogleAuthCallbackInput
    ) -> AuthServiceOutput:
        if not self._is_google_enabled():
            return AuthServiceOutput(
                status=False,
                data=None,
                error="Google login is not configured.",
                code=500,
            )

        try:
            state_payload = self._decode_state_cookie(inputs.state_cookie_value)
            if state_payload.get("type") != _STATE_TOKEN_TYPE:
                return AuthServiceOutput(
                    status=False,
                    data=None,
                    error="Invalid OAuth state.",
                    code=401,
                )
            if str(state_payload.get("state", "")) != inputs.state:
                return AuthServiceOutput(
                    status=False,
                    data=None,
                    error="Invalid OAuth state.",
                    code=401,
                )

            expected_nonce = str(state_payload.get("nonce", "")).strip()
            if not expected_nonce:
                return AuthServiceOutput(
                    status=False,
                    data=None,
                    error="Invalid OAuth state.",
                    code=401,
                )

            token_payload = self._exchange_code_for_tokens(inputs.code)
            claims = self._verify_id_token(
                id_token=str(token_payload["id_token"]),
                expected_nonce=expected_nonce,
            )
            provider_sub = str(claims["sub"])
            email = str(claims["email"])
            email_verified = bool(claims["email_verified"])
            picture_url = claims.get("picture")
            full_name = claims.get("name")
            linked_existing_account = False

            with self._db.get_session() as session:
                identities = self._db.get_user_identities(
                    session=session,
                    filter={
                        "provider": GOOGLE_PROVIDER,
                        "provider_sub": provider_sub,
                    },
                    limit=1,
                )
                identity = identities[0] if identities else None

                if identity is not None:
                    user = self._db.get_user_by_id(session=session, id=identity.user_id)
                    if user is None:
                        return AuthServiceOutput(
                            status=False,
                            data=None,
                            error="Invalid social identity.",
                            code=401,
                        )
                else:
                    users = self._db.get_users(
                        session=session,
                        filter={"email": email},
                        limit=1,
                    )
                    user = users[0] if users else None
                    if user is None:
                        user = self._db.insert_user(
                            session=session,
                            model=User(
                                user_name=self._generate_unique_username(email=email),
                                email=email,
                                password_hash=None,
                                full_name=full_name,
                                phone=None,
                                avatar_url=picture_url,
                                is_active=True,
                                email_verified=email_verified,
                                role="user",
                            ),
                        )
                    else:
                        linked_existing_account = True

                if not user.is_active:
                    return AuthServiceOutput(
                        status=False,
                        data=None,
                        error="User account is inactive.",
                        code=423,
                    )

            persisted_user = self._upsert_identity_for_user(
                user=user,
                provider_sub=provider_sub,
                email=email,
                email_verified=email_verified,
                picture_url=picture_url,
            )
            token_result = self._auth_service.issue_tokens_for_user(
                user=persisted_user,
                ip=inputs.ip,
                user_agent=inputs.user_agent,
            )
            if token_result.status:
                logger.info(
                    "google_login_success",
                    user_id=persisted_user.id,
                    email=email,
                )
                if linked_existing_account:
                    logger.info(
                        "google_linked_existing_account",
                        user_id=persisted_user.id,
                        email=email,
                    )
            return token_result
        except ExpiredSignatureError:
            return AuthServiceOutput(
                status=False,
                data=None,
                error="OAuth state expired.",
                code=401,
            )
        except InvalidTokenError:
            return AuthServiceOutput(
                status=False,
                data=None,
                error="Invalid OAuth state.",
                code=401,
            )
        except GoogleAuthError as exc:
            logger.warning("google_login_failed", reason=exc.message, code=exc.code)
            return AuthServiceOutput(
                status=False,
                data=None,
                error=exc.message,
                code=exc.code,
            )
        except Exception as exc:
            logger.exception("google_login_failed_unexpected", error=str(exc))
            return AuthServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while Google login: {redact_message(str(exc))}",
                code=500,
            )
