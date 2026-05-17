from __future__ import annotations

import hashlib
import hmac
import secrets
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from infra.database.pg import PasswordResetOTP, SQLDatabase
from infra.database.pg.schemas import User
from shared.base import BaseModel
from shared.logging import get_logger, redact_message
from shared.settings import Settings
from shared.settings.models import PostgresSettings

from .auth_service import AuthService

logger = get_logger(__name__)


class PasswordResetServiceOutput(BaseModel):
    status: bool
    data: Any | None = None
    error: str | None = None
    code: int = 200


class SendPasswordResetOtpInput(BaseModel):
    email: str
    ip: str | None = None
    user_agent: str | None = None


class VerifyPasswordResetOtpInput(BaseModel):
    email: str
    otp: str


class ResetPasswordInput(BaseModel):
    reset_token: str
    new_password: str


class PasswordResetService(BaseModel):
    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self._settings = Settings()
        self._db: Any = SQLDatabase(config=PostgresSettings())

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _to_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _normalize_email(value: str) -> str:
        return value.strip().lower()

    @staticmethod
    def _normalize_otp(value: str) -> str:
        return "".join(ch for ch in value.strip() if ch.isdigit())

    def _otp_pepper(self) -> str:
        return self._settings.auth.jwt_secret_key

    def _hash_otp(self, *, email: str, otp: str) -> str:
        raw = f"{email}:{otp}:{self._otp_pepper()}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _otp_matches(self, *, email: str, otp: str, otp_hash: str) -> bool:
        candidate = self._hash_otp(email=email, otp=otp)
        return hmac.compare_digest(candidate, otp_hash)

    def _generate_otp(self) -> str:
        length = self._settings.auth.forgot_password_otp_length
        return "".join(secrets.choice("0123456789") for _ in range(length))

    def _generate_reset_token(
        self, *, otp_id: str, user_id: str, email: str
    ) -> tuple[str, int]:
        now = self._utc_now()
        ttl_minutes = self._settings.auth.forgot_password_reset_token_ttl_minutes
        expires_at = now + timedelta(minutes=ttl_minutes)
        payload = {
            "sub": user_id,
            "email": email,
            "type": "password_reset",
            "jti": otp_id,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        token = jwt.encode(
            payload,
            self._settings.auth.jwt_secret_key,
            algorithm=self._settings.auth.jwt_algorithm,
        )
        expires_in = int((expires_at - now).total_seconds())
        return token, max(expires_in, 0)

    def _decode_reset_token(self, token: str) -> dict[str, Any]:
        return jwt.decode(
            token,
            self._settings.auth.jwt_secret_key,
            algorithms=[self._settings.auth.jwt_algorithm],
            options={"require": ["sub", "email", "type", "jti", "exp"]},
        )

    def _smtp_configured(self) -> bool:
        auth_settings = self._settings.auth
        return bool(
            auth_settings.smtp_host.strip() and auth_settings.smtp_from_email.strip()
        )

    def _send_otp_email(self, *, to_email: str, otp: str) -> None:
        auth_settings = self._settings.auth
        subject = "Your OTP code to reset password"
        text_body = (
            "You requested to reset your password.\n\n"
            f"OTP: {otp}\n"
            f"This code will expire in {auth_settings.forgot_password_otp_ttl_minutes} minutes.\n\n"
            "If you did not request this, please ignore this email."
        )
        html_body = (
            "<p>You requested to reset your password.</p>"
            f"<p><strong>OTP: {otp}</strong></p>"
            f"<p>This code will expire in {auth_settings.forgot_password_otp_ttl_minutes} minutes.</p>"
            "<p>If you did not request this, please ignore this email.</p>"
        )

        message = EmailMessage()
        from_display = auth_settings.smtp_from_name.strip()
        from_email = auth_settings.smtp_from_email.strip()
        message["Subject"] = subject
        message["From"] = (
            f"{from_display} <{from_email}>" if from_display else from_email
        )
        message["To"] = to_email
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")

        if auth_settings.smtp_use_ssl:
            smtp_client: smtplib.SMTP | smtplib.SMTP_SSL = smtplib.SMTP_SSL(
                host=auth_settings.smtp_host,
                port=auth_settings.smtp_port,
                timeout=auth_settings.smtp_timeout_seconds,
            )
        else:
            smtp_client = smtplib.SMTP(
                host=auth_settings.smtp_host,
                port=auth_settings.smtp_port,
                timeout=auth_settings.smtp_timeout_seconds,
            )

        with smtp_client as server:
            if auth_settings.smtp_use_tls and not auth_settings.smtp_use_ssl:
                server.starttls()
            username = auth_settings.smtp_username.strip()
            if username:
                server.login(username, auth_settings.smtp_password)
            server.send_message(message)

    @staticmethod
    def _latest_otp_row(rows: list[PasswordResetOTP] | None) -> PasswordResetOTP | None:
        if not rows:
            return None
        return sorted(
            rows,
            key=lambda row: (
                PasswordResetService._to_utc(
                    row.createdAt or datetime.min.replace(tzinfo=timezone.utc)
                ),
                row.id or "",
            ),
            reverse=True,
        )[0]

    def send_otp(self, inputs: SendPasswordResetOtpInput) -> PasswordResetServiceOutput:
        try:
            auth_settings = self._settings.auth
            if not auth_settings.forgot_password_enabled:
                return PasswordResetServiceOutput(
                    status=False,
                    data=None,
                    error="Forgot password feature is disabled.",
                    code=503,
                )

            email = self._normalize_email(inputs.email)
            if not email:
                return PasswordResetServiceOutput(
                    status=False,
                    data=None,
                    error="Email is required.",
                    code=400,
                )

            now = self._utc_now()
            ttl_seconds = auth_settings.forgot_password_otp_ttl_minutes * 60
            otp_plain = self._generate_otp()
            user: User | None = None
            created_otp_row: PasswordResetOTP | None = None

            with self._db.get_session() as session:
                matched_users = self._db.get_users(
                    session=session,
                    filter={"email": email},
                    limit=1,
                )
                user = matched_users[0] if matched_users else None

                if user is not None:
                    recent_rows = (
                        self._db.get_password_reset_otps(
                            session=session,
                            filter={"email": email},
                        )
                        or []
                    )
                    one_hour_ago = now - timedelta(hours=1)
                    request_count = sum(
                        1
                        for row in recent_rows
                        if self._to_utc(
                            row.createdAt or datetime.min.replace(tzinfo=timezone.utc)
                        )
                        >= one_hour_ago
                    )
                    if (
                        request_count
                        >= auth_settings.forgot_password_otp_max_requests_per_hour
                    ):
                        return PasswordResetServiceOutput(
                            status=False,
                            data=None,
                            error="Too many OTP requests. Please try again later.",
                            code=429,
                        )

                    for row in recent_rows:
                        if row.reset_at is not None:
                            continue
                        if (
                            row.consumed_at is None
                            and self._to_utc(row.expires_at) > now
                        ):
                            row.consumed_at = now
                            self._db.update_password_reset_otp(
                                session=session, model=row
                            )

                    created_otp_row = PasswordResetOTP(
                        id=str(uuid.uuid4()),
                        user_id=str(user.id),
                        email=email,
                        otp_hash=self._hash_otp(email=email, otp=otp_plain),
                        expires_at=now + timedelta(seconds=ttl_seconds),
                        consumed_at=None,
                        reset_at=None,
                        attempt_count=0,
                        ip=inputs.ip,
                        user_agent=inputs.user_agent,
                    )
                    self._db.insert_password_reset_otp(
                        session=session, model=created_otp_row
                    )

            if user is None:
                logger.info("password_reset_send_otp_user_not_found", email=email)
                return PasswordResetServiceOutput(
                    status=False,
                    data=None,
                    error="Email is not registered.",
                    code=404,
                )

            if self._smtp_configured():
                self._send_otp_email(to_email=email, otp=otp_plain)
            elif auth_settings.forgot_password_allow_console_otp_fallback:
                logger.warning(
                    "password_reset_otp_console_fallback",
                    email=email,
                    otp=otp_plain,
                )
            else:
                if created_otp_row is not None:
                    with self._db.get_session() as session:
                        saved = self._db.get_password_reset_otp_by_id(
                            session=session, id=str(created_otp_row.id)
                        )
                        if saved is not None:
                            saved.consumed_at = now
                            self._db.update_password_reset_otp(
                                session=session, model=saved
                            )
                return PasswordResetServiceOutput(
                    status=False,
                    data=None,
                    error="Email service is not configured.",
                    code=500,
                )

            logger.info("password_reset_send_otp_success", email=email)
            return PasswordResetServiceOutput(
                status=True,
                data={
                    "sent": True,
                    "expires_in": ttl_seconds,
                    "message": "OTP sent to your email.",
                },
                error=None,
                code=200,
            )
        except Exception as exc:
            logger.exception("password_reset_send_otp_failed", error=str(exc))
            return PasswordResetServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while sending OTP: {redact_message(str(exc))}",
                code=500,
            )

    def verify_otp(
        self, inputs: VerifyPasswordResetOtpInput
    ) -> PasswordResetServiceOutput:
        try:
            email = self._normalize_email(inputs.email)
            otp = self._normalize_otp(inputs.otp)
            if not email or not otp:
                return PasswordResetServiceOutput(
                    status=False,
                    data=None,
                    error="Email and OTP are required.",
                    code=400,
                )

            if len(otp) != self._settings.auth.forgot_password_otp_length:
                return PasswordResetServiceOutput(
                    status=False,
                    data=None,
                    error="OTP is invalid or expired.",
                    code=401,
                )

            now = self._utc_now()
            with self._db.get_session() as session:
                otp_rows = self._db.get_password_reset_otps(
                    session=session, filter={"email": email}
                )
                otp_row = self._latest_otp_row(otp_rows)
                if otp_row is None:
                    return PasswordResetServiceOutput(
                        status=False,
                        data=None,
                        error="OTP is invalid or expired.",
                        code=401,
                    )

                if otp_row.reset_at is not None:
                    return PasswordResetServiceOutput(
                        status=False,
                        data=None,
                        error="OTP is invalid or expired.",
                        code=401,
                    )

                if (
                    otp_row.consumed_at is not None
                    or self._to_utc(otp_row.expires_at) <= now
                ):
                    return PasswordResetServiceOutput(
                        status=False,
                        data=None,
                        error="OTP is invalid or expired.",
                        code=401,
                    )

                if (
                    otp_row.attempt_count
                    >= self._settings.auth.forgot_password_otp_max_attempts
                ):
                    otp_row.consumed_at = now
                    self._db.update_password_reset_otp(session=session, model=otp_row)
                    return PasswordResetServiceOutput(
                        status=False,
                        data=None,
                        error="OTP is invalid or expired.",
                        code=401,
                    )

                if not self._otp_matches(
                    email=email, otp=otp, otp_hash=otp_row.otp_hash
                ):
                    otp_row.attempt_count += 1
                    if (
                        otp_row.attempt_count
                        >= self._settings.auth.forgot_password_otp_max_attempts
                    ):
                        otp_row.consumed_at = now
                    self._db.update_password_reset_otp(session=session, model=otp_row)
                    return PasswordResetServiceOutput(
                        status=False,
                        data=None,
                        error="OTP is invalid or expired.",
                        code=401,
                    )

                user = self._db.get_user_by_id(session=session, id=str(otp_row.user_id))
                if user is None:
                    return PasswordResetServiceOutput(
                        status=False,
                        data=None,
                        error="OTP is invalid or expired.",
                        code=401,
                    )
                if not user.is_active:
                    return PasswordResetServiceOutput(
                        status=False,
                        data=None,
                        error="User account is inactive.",
                        code=423,
                    )

                otp_row.consumed_at = now
                self._db.update_password_reset_otp(session=session, model=otp_row)

            reset_token, expires_in = self._generate_reset_token(
                otp_id=str(otp_row.id), user_id=str(otp_row.user_id), email=email
            )
            logger.info("password_reset_verify_otp_success", email=email)
            return PasswordResetServiceOutput(
                status=True,
                data={
                    "verified": True,
                    "reset_token": reset_token,
                    "expires_in": expires_in,
                },
                error=None,
                code=200,
            )
        except Exception as exc:
            logger.exception("password_reset_verify_otp_failed", error=str(exc))
            return PasswordResetServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while verifying OTP: {redact_message(str(exc))}",
                code=500,
            )

    def reset_password(self, inputs: ResetPasswordInput) -> PasswordResetServiceOutput:
        try:
            new_password = inputs.new_password.strip()
            if len(new_password) < 8:
                return PasswordResetServiceOutput(
                    status=False,
                    data=None,
                    error="New password must be at least 8 characters.",
                    code=400,
                )

            try:
                payload = self._decode_reset_token(inputs.reset_token)
            except ExpiredSignatureError:
                return PasswordResetServiceOutput(
                    status=False,
                    data=None,
                    error="Reset token is invalid or expired.",
                    code=401,
                )
            except InvalidTokenError:
                return PasswordResetServiceOutput(
                    status=False,
                    data=None,
                    error="Reset token is invalid or expired.",
                    code=401,
                )

            if payload.get("type") != "password_reset":
                return PasswordResetServiceOutput(
                    status=False,
                    data=None,
                    error="Reset token is invalid or expired.",
                    code=401,
                )

            otp_id = str(payload["jti"])
            user_id = str(payload["sub"])
            email = self._normalize_email(str(payload["email"]))
            now = self._utc_now()

            with self._db.get_session() as session:
                otp_row = self._db.get_password_reset_otp_by_id(
                    session=session, id=otp_id
                )
                if otp_row is None:
                    return PasswordResetServiceOutput(
                        status=False,
                        data=None,
                        error="Reset token is invalid or expired.",
                        code=401,
                    )

                if (
                    str(otp_row.user_id) != user_id
                    or self._normalize_email(otp_row.email) != email
                    or otp_row.consumed_at is None
                    or otp_row.reset_at is not None
                ):
                    return PasswordResetServiceOutput(
                        status=False,
                        data=None,
                        error="Reset token is invalid or expired.",
                        code=401,
                    )

                user = self._db.get_user_by_id(session=session, id=user_id)
                if user is None:
                    return PasswordResetServiceOutput(
                        status=False, data=None, error="User not found.", code=404
                    )
                if not user.is_active:
                    return PasswordResetServiceOutput(
                        status=False,
                        data=None,
                        error="User account is inactive.",
                        code=423,
                    )

                user.password_hash = AuthService.hash_password(new_password)
                self._db.update_user(session=session, model=user)

                otp_row.reset_at = now
                self._db.update_password_reset_otp(session=session, model=otp_row)

            logger.info("password_reset_success", user_id=user_id)
            return PasswordResetServiceOutput(
                status=True,
                data={"reset": True},
                error=None,
                code=200,
            )
        except Exception as exc:
            logger.exception("password_reset_failed", error=str(exc))
            return PasswordResetServiceOutput(
                status=False,
                data=None,
                error=f"Unexpected error while resetting password: {redact_message(str(exc))}",
                code=500,
            )
