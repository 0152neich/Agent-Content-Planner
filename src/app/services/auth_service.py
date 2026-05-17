from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from passlib.context import CryptContext

from infra.database.pg import SQLDatabase
from infra.database.pg.schemas import RefreshToken, User
from shared.base import BaseModel
from shared.logging import get_logger, redact_message
from shared.settings import Settings
from shared.settings.models import PostgresSettings

logger = get_logger(__name__)


pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


class AuthServiceOutput(BaseModel):
    status: bool
    data: Any | None = None
    error: str | None = None
    code: int = 200


class LoginInput(BaseModel):
    identifier: str
    password: str
    ip: str | None = None
    user_agent: str | None = None


class RefreshInput(BaseModel):
    refresh_token: str
    ip: str | None = None
    user_agent: str | None = None


class LogoutInput(BaseModel):
    refresh_token: str | None = None


class ValidateAccessTokenInput(BaseModel):
    access_token: str


class AuthService(BaseModel):
    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self._settings = Settings()
        self._db = SQLDatabase(config=PostgresSettings())

    @staticmethod
    def hash_password(plain_password: str) -> str:
        return pwd_context.hash(plain_password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str | None) -> bool:
        if not hashed_password:
            return False
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            return False

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _hash_refresh_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _to_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _encode_token(
        self,
        *,
        user_id: str,
        token_type: str,
        expires_delta: timedelta,
        jti: str,
    ) -> tuple[str, datetime]:
        now = self._utc_now()
        expires_at = now + expires_delta
        payload = {
            "sub": user_id,
            "type": token_type,
            "jti": jti,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        token = jwt.encode(
            payload,
            self._settings.auth.jwt_secret_key,
            algorithm=self._settings.auth.jwt_algorithm,
        )
        return token, expires_at

    def _decode_token(self, token: str) -> dict[str, Any]:
        return jwt.decode(
            token,
            self._settings.auth.jwt_secret_key,
            algorithms=[self._settings.auth.jwt_algorithm],
            options={"require": ["sub", "type", "jti", "exp"]},
        )

    def _find_user_by_identifier(self, identifier: str) -> User | None:
        with self._db.get_session() as session:
            users = self._db.get_users(
                session=session, filter={"email": identifier}, limit=1
            )
            if users:
                return users[0]
            users = self._db.get_users(
                session=session, filter={"user_name": identifier}, limit=1
            )
            return users[0] if users else None

    def _build_access_payload(self, user: User) -> dict[str, Any]:
        access_jti = str(uuid.uuid4())
        access_token, access_expires_at = self._encode_token(
            user_id=str(user.id),
            token_type="access",
            expires_delta=timedelta(
                minutes=self._settings.auth.access_token_ttl_minutes
            ),
            jti=access_jti,
        )
        expires_in = int((access_expires_at - self._utc_now()).total_seconds())
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": max(expires_in, 0),
            "user": user,
        }

    def _create_refresh_token(
        self,
        *,
        user_id: str,
        ip: str | None,
        user_agent: str | None,
    ) -> tuple[str, RefreshToken]:
        refresh_jti = str(uuid.uuid4())
        refresh_token, refresh_expires_at = self._encode_token(
            user_id=user_id,
            token_type="refresh",
            expires_delta=timedelta(days=self._settings.auth.refresh_token_ttl_days),
            jti=refresh_jti,
        )
        refresh_model = RefreshToken(
            id=refresh_jti,
            user_id=user_id,
            token_hash=self._hash_refresh_token(refresh_token),
            expires_at=refresh_expires_at,
            revoked_at=None,
            replaced_by_jti=None,
            ip=ip,
            user_agent=user_agent,
        )
        return refresh_token, refresh_model

    def _revoke_all_active_refresh_tokens(self, *, user_id: str, now: datetime) -> None:
        with self._db.get_session() as session:
            tokens = (
                self._db.get_refresh_tokens(
                    session=session, filter={"user_id": user_id}
                )
                or []
            )
            for token_row in tokens:
                if (
                    token_row.revoked_at is None
                    and self._to_utc(token_row.expires_at) > now
                ):
                    token_row.revoked_at = now
                    self._db.update_refresh_token(session=session, model=token_row)

    def issue_tokens_for_user(
        self, *, user: User, ip: str | None = None, user_agent: str | None = None
    ) -> AuthServiceOutput:
        try:
            if not user.is_active:
                return AuthServiceOutput(
                    status=False,
                    data=None,
                    error="User account is inactive.",
                    code=423,
                )

            access_payload = self._build_access_payload(user)
            refresh_token, refresh_model = self._create_refresh_token(
                user_id=str(user.id),
                ip=ip,
                user_agent=user_agent,
            )

            with self._db.get_session() as session:
                self._db.insert_refresh_token(session=session, model=refresh_model)

            return AuthServiceOutput(
                status=True,
                data={**access_payload, "refresh_token": refresh_token},
                error=None,
                code=200,
            )
        except Exception as exc:
            logger.exception("issue_tokens_failed_unexpected", error=str(exc))
            return AuthServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while issuing tokens: {redact_message(str(exc))}",
                code=500,
            )

    def login(self, inputs: LoginInput) -> AuthServiceOutput:
        try:
            user = self._find_user_by_identifier(inputs.identifier)
            if user is None:
                logger.warning(
                    "login_failed",
                    reason="invalid_credentials",
                    identifier=inputs.identifier,
                )
                return AuthServiceOutput(
                    status=False,
                    data=None,
                    error="username or password is invalid",
                    code=401,
                )

            if not user.is_active:
                logger.warning("login_failed", reason="inactive_user", user_id=user.id)
                return AuthServiceOutput(
                    status=False, data=None, error="User account is inactive.", code=423
                )

            if not self.verify_password(inputs.password, user.password_hash):
                logger.warning(
                    "login_failed", reason="invalid_credentials", user_id=user.id
                )
                return AuthServiceOutput(
                    status=False,
                    data=None,
                    error="username or password is invalid",
                    code=401,
                )

            token_result = self.issue_tokens_for_user(
                user=user,
                ip=inputs.ip,
                user_agent=inputs.user_agent,
            )
            if not token_result.status:
                return token_result

            logger.info("login_success", user_id=user.id)
            return token_result
        except Exception as exc:
            logger.exception("login_failed_unexpected", error=str(exc))
            return AuthServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while login: {redact_message(str(exc))}",
                code=500,
            )

    def refresh(self, inputs: RefreshInput) -> AuthServiceOutput:
        now = self._utc_now()
        try:
            try:
                payload = self._decode_token(inputs.refresh_token)
            except ExpiredSignatureError:
                return AuthServiceOutput(
                    status=False, data=None, error="Invalid refresh token.", code=401
                )
            except InvalidTokenError:
                return AuthServiceOutput(
                    status=False, data=None, error="Invalid refresh token.", code=401
                )

            if payload.get("type") != "refresh":
                return AuthServiceOutput(
                    status=False, data=None, error="Invalid refresh token.", code=401
                )

            jti = str(payload["jti"])
            user_id = str(payload["sub"])
            token_hash = self._hash_refresh_token(inputs.refresh_token)

            with self._db.get_session() as session:
                token_row = self._db.get_refresh_token_by_id(session=session, id=jti)
                if token_row is None:
                    return AuthServiceOutput(
                        status=False,
                        data=None,
                        error="Invalid refresh token.",
                        code=401,
                    )

                if token_row.user_id != user_id or token_row.token_hash != token_hash:
                    return AuthServiceOutput(
                        status=False,
                        data=None,
                        error="Invalid refresh token.",
                        code=401,
                    )

                if self._to_utc(token_row.expires_at) <= now:
                    token_row.revoked_at = now
                    self._db.update_refresh_token(session=session, model=token_row)
                    return AuthServiceOutput(
                        status=False,
                        data=None,
                        error="Invalid refresh token.",
                        code=401,
                    )

                if token_row.revoked_at is not None:
                    logger.warning(
                        "refresh_token_reuse_detected", user_id=user_id, jti=jti
                    )
                    self._revoke_all_active_refresh_tokens(user_id=user_id, now=now)
                    return AuthServiceOutput(
                        status=False,
                        data=None,
                        error="Invalid refresh token.",
                        code=401,
                    )

                user = self._db.get_user_by_id(session=session, id=user_id)
                if user is None:
                    return AuthServiceOutput(
                        status=False, data=None, error="User not found.", code=404
                    )
                if not user.is_active:
                    return AuthServiceOutput(
                        status=False,
                        data=None,
                        error="User account is inactive.",
                        code=423,
                    )

                access_payload = self._build_access_payload(user)
                new_refresh_token, new_refresh_model = self._create_refresh_token(
                    user_id=user_id,
                    ip=inputs.ip,
                    user_agent=inputs.user_agent,
                )

                token_row.revoked_at = now
                token_row.replaced_by_jti = new_refresh_model.id
                self._db.update_refresh_token(session=session, model=token_row)
                self._db.insert_refresh_token(session=session, model=new_refresh_model)

            logger.info("refresh_success", user_id=user_id)
            return AuthServiceOutput(
                status=True,
                data={**access_payload, "refresh_token": new_refresh_token},
                error=None,
                code=200,
            )
        except Exception as exc:
            logger.exception("refresh_failed_unexpected", error=str(exc))
            return AuthServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while refresh: {redact_message(str(exc))}",
                code=500,
            )

    def logout(self, inputs: LogoutInput) -> AuthServiceOutput:
        if not inputs.refresh_token:
            return AuthServiceOutput(
                status=True, data={"logged_out": True}, error=None, code=200
            )

        try:
            payload = self._decode_token(inputs.refresh_token)
            if payload.get("type") != "refresh":
                return AuthServiceOutput(
                    status=True, data={"logged_out": True}, error=None, code=200
                )

            jti = str(payload["jti"])
            now = self._utc_now()
            with self._db.get_session() as session:
                token_row = self._db.get_refresh_token_by_id(session=session, id=jti)
                if token_row is not None and token_row.revoked_at is None:
                    token_row.revoked_at = now
                    self._db.update_refresh_token(session=session, model=token_row)
            logger.info("logout_success", jti=jti)
            return AuthServiceOutput(
                status=True, data={"logged_out": True}, error=None, code=200
            )
        except (ExpiredSignatureError, InvalidTokenError):
            return AuthServiceOutput(
                status=True, data={"logged_out": True}, error=None, code=200
            )
        except Exception as exc:
            logger.exception("logout_failed_unexpected", error=str(exc))
            return AuthServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while logout: {redact_message(str(exc))}",
                code=500,
            )

    def validate_access_token(
        self, inputs: ValidateAccessTokenInput
    ) -> AuthServiceOutput:
        try:
            payload = self._decode_token(inputs.access_token)
            if payload.get("type") != "access":
                return AuthServiceOutput(
                    status=False, data=None, error="Invalid access token.", code=401
                )

            user_id = str(payload["sub"])
            with self._db.get_session() as session:
                user = self._db.get_user_by_id(session=session, id=user_id)
            if user is None:
                return AuthServiceOutput(
                    status=False, data=None, error="User not found.", code=404
                )
            if not user.is_active:
                return AuthServiceOutput(
                    status=False, data=None, error="User account is inactive.", code=423
                )
            return AuthServiceOutput(status=True, data=user, error=None, code=200)
        except ExpiredSignatureError:
            return AuthServiceOutput(
                status=False, data=None, error="Invalid access token.", code=401
            )
        except InvalidTokenError:
            return AuthServiceOutput(
                status=False, data=None, error="Invalid access token.", code=401
            )
        except Exception as exc:
            logger.exception("access_validation_failed_unexpected", error=str(exc))
            return AuthServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while validating access token: {redact_message(str(exc))}",
                code=500,
            )
