"""Abstract interface for PasswordResetOTP persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from sqlalchemy.orm import Session

from ..schemas import PasswordResetOTP


class PasswordResetOTPRepository(ABC):
    @abstractmethod
    def insert_password_reset_otp(
        self, session: Session, model: PasswordResetOTP
    ) -> PasswordResetOTP:
        raise NotImplementedError

    @abstractmethod
    def update_password_reset_otp(
        self, session: Session, model: PasswordResetOTP
    ) -> PasswordResetOTP | None:
        raise NotImplementedError

    @abstractmethod
    def get_password_reset_otp_by_id(
        self, session: Session, id: str
    ) -> PasswordResetOTP | None:
        raise NotImplementedError

    @abstractmethod
    def get_password_reset_otps(
        self,
        session: Session,
        filter: dict[str, object] | None = None,
        order_by: Sequence | None = None,
        limit: int | None = None,
    ) -> list[PasswordResetOTP] | None:
        raise NotImplementedError
