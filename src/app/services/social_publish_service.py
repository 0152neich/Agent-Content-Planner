from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

from infra.database.pg import SQLDatabase
from infra.database.pg.schemas import SocialConnection
from shared.base import BaseModel
from shared.logging import get_logger, redact_message
from shared.settings.models import PostgresSettings

from .social_token_cipher_service import SocialTokenCipherService

logger = get_logger(__name__)

LINKEDIN_PROVIDER = "linkedin"
FACEBOOK_PROVIDER = "facebook"
FACEBOOK_PAGES_URL = "https://graph.facebook.com/v19.0/me/accounts"


class SocialPublishInput(BaseModel):
    user_id: str
    platform: str
    content: str
    page_id: str | None = None


class SocialPublishServiceOutput(BaseModel):
    status: bool
    data: Any | None = None
    error: str | None = None
    error_code: str | None = None
    code: int = 200


class SocialPublishService(BaseModel):
    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self._db = SQLDatabase(config=PostgresSettings())
        self._cipher = SocialTokenCipherService()
        self._timeout_seconds = 20

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _normalize_platform(platform: str | None) -> str:
        return (platform or "").strip().lower()

    @staticmethod
    def _extract_error_message(payload: Any, fallback: str) -> str:
        if isinstance(payload, dict):
            top_message = payload.get("message")
            if isinstance(top_message, str) and top_message.strip():
                return top_message.strip()
            nested_error = payload.get("error")
            if isinstance(nested_error, dict):
                nested_message = nested_error.get("message")
                if isinstance(nested_message, str) and nested_message.strip():
                    return nested_message.strip()
        return fallback

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
    def _build_linkedin_view_url(provider_post_id: str) -> str:
        return f"https://www.linkedin.com/feed/update/{provider_post_id.strip()}/"

    @staticmethod
    def _build_facebook_view_url(provider_post_id: str) -> str:
        return f"https://www.facebook.com/{provider_post_id.strip()}"

    def _get_connection(self, user_id: str, provider: str) -> SocialConnection | None:
        with self._db.get_session() as session:
            rows = self._db.get_social_connections(
                session=session,
                filter={"user_id": user_id, "provider": provider},
                limit=1,
            )
        return rows[0] if rows else None

    def _resolve_access_token(
        self, user_id: str, provider: str, provider_name: str
    ) -> tuple[str, SocialConnection] | SocialPublishServiceOutput:
        connection = self._get_connection(user_id=user_id, provider=provider)
        if not connection or connection.revoked_at is not None:
            return SocialPublishServiceOutput(
                status=False,
                data=None,
                error=f"{provider_name} account is not connected.",
                error_code="SOCIAL_NOT_CONNECTED",
                code=400,
            )

        if not connection.access_token_encrypted.strip():
            return SocialPublishServiceOutput(
                status=False,
                data=None,
                error=f"{provider_name} account is not connected.",
                error_code="SOCIAL_NOT_CONNECTED",
                code=400,
            )

        expires_at = connection.token_expires_at
        if expires_at is not None:
            now = self._utc_now()
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= now:
                return SocialPublishServiceOutput(
                    status=False,
                    data=None,
                    error=f"{provider_name} access token has expired. Please reconnect your account.",
                    error_code="SOCIAL_TOKEN_EXPIRED",
                    code=401,
                )
        try:
            access_token = self._cipher.decrypt(connection.access_token_encrypted)
        except ValueError as exc:
            if "AUTH__SOCIAL_TOKEN_ENCRYPTION_KEY" in str(exc):
                return SocialPublishServiceOutput(
                    status=False,
                    data=None,
                    error="Social token encryption key is not configured.",
                    error_code="SOCIAL_CONFIG_INVALID",
                    code=500,
                )
            return SocialPublishServiceOutput(
                status=False,
                data=None,
                error=f"Invalid stored {provider_name} credentials. Please reconnect your account.",
                error_code="SOCIAL_TOKEN_INVALID",
                code=401,
            )

        return access_token, connection

    def _resolve_linkedin_credentials(
        self, user_id: str
    ) -> tuple[str, str] | SocialPublishServiceOutput:
        token = self._resolve_access_token(
            user_id=user_id, provider=LINKEDIN_PROVIDER, provider_name="LinkedIn"
        )
        if isinstance(token, SocialPublishServiceOutput):
            return token
        access_token, connection = token
        author_urn = str(connection.provider_account_id or "").strip()
        if not author_urn:
            return SocialPublishServiceOutput(
                status=False,
                data=None,
                error="LinkedIn account metadata is missing. Please reconnect your account.",
                error_code="SOCIAL_NOT_CONNECTED",
                code=400,
            )
        return access_token, author_urn

    def _publish_linkedin(
        self, user_id: str, content: str
    ) -> SocialPublishServiceOutput:
        credentials = self._resolve_linkedin_credentials(user_id=user_id)
        if isinstance(credentials, SocialPublishServiceOutput):
            return credentials
        access_token, author_urn = credentials

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }
        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": content},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        try:
            response = requests.post(
                "https://api.linkedin.com/v2/ugcPosts",
                headers=headers,
                json=payload,
                timeout=self._timeout_seconds,
            )
        except requests.RequestException as exc:
            logger.warning(
                "linkedin_publish_network_error", error=redact_message(str(exc))
            )
            return SocialPublishServiceOutput(
                status=False,
                data=None,
                error="Unable to reach LinkedIn API. Please try again.",
                error_code="SOCIAL_PROVIDER_NETWORK_ERROR",
                code=400,
            )

        response_payload = self._safe_json(response)
        if response.status_code not in {200, 201}:
            error_message = self._extract_error_message(
                response_payload,
                f"LinkedIn publish failed with status {response.status_code}.",
            )
            lowered = error_message.lower()
            if (
                response.status_code in {401, 403}
                or "token" in lowered
                or "oauth" in lowered
            ):
                return SocialPublishServiceOutput(
                    status=False,
                    data=None,
                    error="LinkedIn token expired or revoked. Please reconnect your account.",
                    error_code="SOCIAL_TOKEN_EXPIRED",
                    code=401,
                )
            return SocialPublishServiceOutput(
                status=False,
                data=None,
                error=error_message,
                error_code="SOCIAL_PROVIDER_ERROR",
                code=400,
            )

        provider_post_id = str(
            response_payload.get("id") or response.headers.get("x-restli-id") or ""
        ).strip()
        if not provider_post_id:
            return SocialPublishServiceOutput(
                status=False,
                data=None,
                error="LinkedIn did not return a post id.",
                error_code="SOCIAL_PROVIDER_ERROR",
                code=400,
            )

        return SocialPublishServiceOutput(
            status=True,
            data={
                "platform": "linkedin",
                "provider_post_id": provider_post_id,
                "view_url": self._build_linkedin_view_url(provider_post_id),
            },
            error=None,
            error_code=None,
            code=200,
        )

    def _resolve_facebook_page_token(
        self, *, user_id: str, page_id: str
    ) -> tuple[str, dict[str, Any]] | SocialPublishServiceOutput:
        token = self._resolve_access_token(
            user_id=user_id, provider=FACEBOOK_PROVIDER, provider_name="Facebook"
        )
        if isinstance(token, SocialPublishServiceOutput):
            return token
        user_access_token, _ = token

        params = {
            "fields": "id,name,tasks,access_token",
            "access_token": user_access_token,
        }
        try:
            response = requests.get(
                FACEBOOK_PAGES_URL, params=params, timeout=self._timeout_seconds
            )
        except requests.RequestException as exc:
            logger.warning(
                "facebook_pages_network_error", error=redact_message(str(exc))
            )
            return SocialPublishServiceOutput(
                status=False,
                data=None,
                error="Unable to reach Facebook API. Please try again.",
                error_code="SOCIAL_PROVIDER_NETWORK_ERROR",
                code=400,
            )
        payload = self._safe_json(response)
        if response.status_code != 200:
            message = self._extract_error_message(
                payload, "Failed to fetch Facebook pages."
            )
            lowered = message.lower()
            if (
                response.status_code in {401, 403}
                or "token" in lowered
                or "oauth" in lowered
            ):
                return SocialPublishServiceOutput(
                    status=False,
                    data=None,
                    error="Facebook token expired or revoked. Please reconnect your account.",
                    error_code="SOCIAL_TOKEN_EXPIRED",
                    code=401,
                )
            return SocialPublishServiceOutput(
                status=False,
                data=None,
                error=message,
                error_code="SOCIAL_PROVIDER_ERROR",
                code=400,
            )
        rows = payload.get("data")
        if not isinstance(rows, list):
            rows = []
        normalized_page_id = page_id.strip()
        for row in rows:
            if not isinstance(row, dict):
                continue
            if str(row.get("id") or "").strip() == normalized_page_id:
                page_token = str(row.get("access_token") or "").strip()
                if not page_token:
                    return SocialPublishServiceOutput(
                        status=False,
                        data=None,
                        error="Facebook page access token is missing.",
                        error_code="SOCIAL_PAGE_PERMISSION_DENIED",
                        code=400,
                    )
                return page_token, row
        return SocialPublishServiceOutput(
            status=False,
            data=None,
            error="Selected Facebook page is not available for this account.",
            error_code="SOCIAL_PAGE_NOT_FOUND",
            code=400,
        )

    def _publish_facebook(
        self, *, user_id: str, content: str, page_id: str
    ) -> SocialPublishServiceOutput:
        credentials = self._resolve_facebook_page_token(
            user_id=user_id, page_id=page_id
        )
        if isinstance(credentials, SocialPublishServiceOutput):
            return credentials
        page_token, _page = credentials

        url = f"https://graph.facebook.com/v19.0/{page_id.strip()}/feed"
        try:
            response = requests.post(
                url,
                data={"message": content, "access_token": page_token},
                timeout=self._timeout_seconds,
            )
        except requests.RequestException as exc:
            logger.warning(
                "facebook_publish_network_error", error=redact_message(str(exc))
            )
            return SocialPublishServiceOutput(
                status=False,
                data=None,
                error="Unable to reach Facebook API. Please try again.",
                error_code="SOCIAL_PROVIDER_NETWORK_ERROR",
                code=400,
            )

        payload = self._safe_json(response)
        if response.status_code not in {200, 201}:
            message = self._extract_error_message(
                payload, f"Facebook publish failed with status {response.status_code}."
            )
            lowered = message.lower()
            error_obj = payload.get("error") if isinstance(payload, dict) else None
            code_raw: object | None = None
            if isinstance(error_obj, dict):
                code_raw = error_obj.get("code")
            error_code = (
                int(code_raw)
                if isinstance(code_raw, (int, str)) and str(code_raw).isdigit()
                else None
            )
            if (
                response.status_code in {401, 403}
                or "token" in lowered
                or "oauth" in lowered
            ):
                return SocialPublishServiceOutput(
                    status=False,
                    data=None,
                    error="Facebook token expired or revoked. Please reconnect your account.",
                    error_code="SOCIAL_TOKEN_EXPIRED",
                    code=401,
                )
            if error_code == 200 or "permission" in lowered or "admin" in lowered:
                return SocialPublishServiceOutput(
                    status=False,
                    data=None,
                    error=message,
                    error_code="SOCIAL_PAGE_PERMISSION_DENIED",
                    code=400,
                )
            return SocialPublishServiceOutput(
                status=False,
                data=None,
                error=message,
                error_code="SOCIAL_PROVIDER_ERROR",
                code=400,
            )
        provider_post_id = str(payload.get("id") or "").strip()
        if not provider_post_id:
            return SocialPublishServiceOutput(
                status=False,
                data=None,
                error="Facebook did not return a post id.",
                error_code="SOCIAL_PROVIDER_ERROR",
                code=400,
            )
        return SocialPublishServiceOutput(
            status=True,
            data={
                "platform": "facebook",
                "provider_post_id": provider_post_id,
                "view_url": self._build_facebook_view_url(provider_post_id),
            },
            error=None,
            error_code=None,
            code=200,
        )

    def schedule_facebook(
        self,
        *,
        user_id: str,
        content: str,
        page_id: str,
        scheduled_at: datetime,
    ) -> SocialPublishServiceOutput:
        credentials = self._resolve_facebook_page_token(
            user_id=user_id, page_id=page_id
        )
        if isinstance(credentials, SocialPublishServiceOutput):
            return credentials
        page_token, _page = credentials
        scheduled_at_utc = (
            scheduled_at.replace(tzinfo=timezone.utc)
            if scheduled_at.tzinfo is None
            else scheduled_at.astimezone(timezone.utc)
        )
        scheduled_publish_time = int(scheduled_at_utc.timestamp())

        url = f"https://graph.facebook.com/v19.0/{page_id.strip()}/feed"
        try:
            response = requests.post(
                url,
                data={
                    "message": content,
                    "published": "false",
                    "scheduled_publish_time": str(scheduled_publish_time),
                    "access_token": page_token,
                },
                timeout=self._timeout_seconds,
            )
        except requests.RequestException as exc:
            logger.warning(
                "facebook_schedule_network_error", error=redact_message(str(exc))
            )
            return SocialPublishServiceOutput(
                status=False,
                data=None,
                error="Unable to reach Facebook API. Please try again.",
                error_code="SOCIAL_PROVIDER_NETWORK_ERROR",
                code=400,
            )

        payload = self._safe_json(response)
        if response.status_code not in {200, 201}:
            message = self._extract_error_message(
                payload, f"Facebook schedule failed with status {response.status_code}."
            )
            error_obj = payload.get("error") if isinstance(payload, dict) else None
            provider_error_code: int | None = None
            if isinstance(error_obj, dict):
                code_raw = error_obj.get("code")
                if isinstance(code_raw, int):
                    provider_error_code = code_raw
                elif isinstance(code_raw, str) and code_raw.isdigit():
                    provider_error_code = int(code_raw)
            lowered = message.lower()
            if provider_error_code == 190 or "oauth" in lowered or "token" in lowered:
                return SocialPublishServiceOutput(
                    status=False,
                    data=None,
                    error="Facebook token expired or revoked. Please reconnect your account.",
                    error_code="SOCIAL_TOKEN_EXPIRED",
                    code=401,
                )
            return SocialPublishServiceOutput(
                status=False,
                data=None,
                error=message,
                error_code="SOCIAL_PROVIDER_ERROR",
                code=400,
            )

        provider_post_id = str(payload.get("id") or "").strip()
        if not provider_post_id:
            return SocialPublishServiceOutput(
                status=False,
                data=None,
                error="Facebook did not return a post id.",
                error_code="SOCIAL_PROVIDER_ERROR",
                code=400,
            )
        return SocialPublishServiceOutput(
            status=True,
            data={
                "platform": "facebook",
                "provider_post_id": provider_post_id,
                "provider_schedule_id": provider_post_id,
                "view_url": self._build_facebook_view_url(provider_post_id),
            },
            error=None,
            error_code=None,
            code=200,
        )

    def publish(self, inputs: SocialPublishInput) -> SocialPublishServiceOutput:
        try:
            platform = self._normalize_platform(inputs.platform)
            content = inputs.content.strip()
            user_id = inputs.user_id.strip()
            page_id = (inputs.page_id or "").strip()
            if not user_id:
                return SocialPublishServiceOutput(
                    status=False,
                    data=None,
                    error="Invalid user context.",
                    error_code="SOCIAL_INVALID_USER",
                    code=400,
                )
            if not content:
                return SocialPublishServiceOutput(
                    status=False,
                    data=None,
                    error="Content must not be blank.",
                    error_code="SOCIAL_INVALID_CONTENT",
                    code=400,
                )
            if platform not in {"linkedin", "facebook"}:
                return SocialPublishServiceOutput(
                    status=False,
                    data=None,
                    error="Unsupported platform. Allowed: linkedin, facebook.",
                    error_code="SOCIAL_UNSUPPORTED_PLATFORM",
                    code=400,
                )
            if platform == "linkedin":
                return self._publish_linkedin(user_id, content)
            if not page_id:
                return SocialPublishServiceOutput(
                    status=False,
                    data=None,
                    error="page_id is required when publishing to facebook.",
                    error_code="SOCIAL_PAGE_ID_REQUIRED",
                    code=400,
                )
            return self._publish_facebook(
                user_id=user_id, content=content, page_id=page_id
            )
        except Exception as exc:
            logger.exception(
                "social_publish_unexpected_error", error=redact_message(str(exc))
            )
            return SocialPublishServiceOutput(
                status=False,
                data=None,
                error="Unexpected error while publishing post.",
                error_code="SOCIAL_UNEXPECTED_ERROR",
                code=500,
            )
