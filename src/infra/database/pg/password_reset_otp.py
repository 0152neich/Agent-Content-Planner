"""Password reset OTP repository implementation."""

from __future__ import annotations

from collections.abc import Sequence
from functools import partial
from typing import cast

from shared.logging import get_logger
from sqlalchemy.orm import Session

from .models import PasswordResetOTP as PasswordResetOTPModel
from .repositories import PasswordResetOTPRepository
from .schemas import PasswordResetOTP
from .utils import _get_data, _get_data_by_id, _insert, _update

logger = get_logger(__name__)

_insert_password_reset_otp = partial(
    _insert, logger, PasswordResetOTPModel, PasswordResetOTP
)
_update_password_reset_otp = partial(
    _update, logger, PasswordResetOTPModel, PasswordResetOTP
)
_get_password_reset_otp_by_id = partial(
    _get_data_by_id, logger, PasswordResetOTPModel, PasswordResetOTP
)
_get_password_reset_otps = partial(
    _get_data, logger, PasswordResetOTPModel, PasswordResetOTP
)


class PasswordResetOTPRepositoryImpl(PasswordResetOTPRepository):
    def insert_password_reset_otp(
        self, session: Session, model: PasswordResetOTP
    ) -> PasswordResetOTP:
        return cast(PasswordResetOTP, _insert_password_reset_otp(session, model))

    def update_password_reset_otp(
        self, session: Session, model: PasswordResetOTP
    ) -> PasswordResetOTP | None:
        result = _update_password_reset_otp(session, model)
        return cast(PasswordResetOTP, result) if result else None

    def get_password_reset_otp_by_id(
        self, session: Session, id: str
    ) -> PasswordResetOTP | None:
        result = _get_password_reset_otp_by_id(session, id)
        return cast(PasswordResetOTP, result) if result else None

    def get_password_reset_otps(
        self,
        session: Session,
        filter: dict[str, object] | None = None,
        order_by: Sequence | None = None,
        limit: int | None = None,
    ) -> list[PasswordResetOTP] | None:
        result = _get_password_reset_otps(session, filter, order_by, limit)
        return cast(list[PasswordResetOTP], result) if result else None
