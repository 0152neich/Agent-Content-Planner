"""Generic CRUD helpers for ORM models with Dated (soft-delete) support."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from datetime import timezone

from sqlalchemy import select
from sqlalchemy.orm import Session
from structlog.stdlib import BoundLogger

from .models import Base
from .schemas import DatabaseSchema


def _has_deleted_at(model_cls: type[Base]) -> bool:
    return hasattr(model_cls, "__table__") and "deletedAt" in model_cls.__table__.c


def _insert(
    logger: BoundLogger,
    model_cls: type[Base],
    schema_cls: type[DatabaseSchema],
    session: Session,
    data: DatabaseSchema,
) -> DatabaseSchema:
    try:
        payload = data.model_dump(exclude_none=True)
        if not payload.get("id"):
            payload["id"] = str(uuid.uuid4())
        obj = model_cls(**payload)
        session.add(obj)
        session.commit()
        session.refresh(obj)
        return schema_cls.model_validate(obj)
    except Exception as e:
        logger.exception(f"Error inserting {schema_cls}: {e}", channel=data)
        raise


def _update(
    logger: BoundLogger,
    model_cls: type[Base],
    schema_cls: type[DatabaseSchema],
    session: Session,
    data: DatabaseSchema,
) -> DatabaseSchema | None:
    try:
        obj = session.get(model_cls, data.id)
        if obj:
            payload = data.model_dump(exclude_none=True, exclude={"id", "createdAt"})
            # Preserve explicit null updates (e.g. revoked_at=None on reconnect)
            # while still ignoring unspecified fields.
            for field_name in data.model_fields_set:
                if field_name in {"id", "createdAt"}:
                    continue
                if getattr(data, field_name, None) is None:
                    payload[field_name] = None
            for k, v in payload.items():
                if hasattr(obj, k):
                    setattr(obj, k, v)
            session.add(obj)
            session.commit()
            session.refresh(obj)
            return schema_cls.model_validate(obj)
        logger.info(f"No {schema_cls} found with id: {data.id}")
        return None
    except Exception as e:
        logger.exception(f"Error updating {schema_cls}: {e}", channel=data)
        raise


def _get_data(
    logger: BoundLogger,
    model_cls: type[Base],
    schema_cls: type[DatabaseSchema],
    session: Session,
    filter: dict[str, object] | None = None,
    order_by: Sequence | None = None,
    limit: int | None = None,
) -> list[DatabaseSchema] | None:
    try:
        statement = select(model_cls)
        if _has_deleted_at(model_cls):
            statement = statement.where(model_cls.deletedAt.is_(None))
        if filter:
            statement = statement.filter_by(**filter)
        if order_by:
            statement = statement.order_by(*order_by)
        if limit:
            statement = statement.limit(limit)
        objs = session.scalars(statement).all()
        if not objs:
            return None
        return [schema_cls.model_validate(o) for o in objs]
    except Exception as e:
        logger.exception(
            f"Error fetching {schema_cls}: {e}",
            filter=filter,
            limit=limit,
        )
        raise


def _get_data_by_id(
    logger: BoundLogger,
    model_cls: type[Base],
    schema_cls: type[DatabaseSchema],
    session: Session,
    id: str,
) -> DatabaseSchema | None:
    try:
        obj = session.get(model_cls, id)
        if not obj:
            return None
        if _has_deleted_at(model_cls) and getattr(obj, "deletedAt", None) is not None:
            return None
        return schema_cls.model_validate(obj)
    except Exception as e:
        logger.exception(f"Error fetching {schema_cls}: {e}", id=id)
        raise


def _delete(
    logger: BoundLogger,
    model_cls: type[Base],
    schema_cls: type[DatabaseSchema],
    session: Session,
    id: str,
) -> DatabaseSchema | None:
    try:
        obj = session.get(model_cls, id)
        if not obj:
            logger.info(f"No {schema_cls} found with id: {id}")
            return None
        if _has_deleted_at(model_cls):
            obj.deletedAt = datetime.now(timezone.utc)
            session.add(obj)
            session.commit()
            session.refresh(obj)
            return schema_cls.model_validate(obj)
        session.delete(obj)
        session.commit()
        return schema_cls.model_validate(obj)
    except Exception as e:
        logger.exception(f"Error deleting {schema_cls}: {e}", id=id)
        raise
