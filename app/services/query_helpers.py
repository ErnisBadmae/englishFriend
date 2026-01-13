"""Database query helpers to reduce repetitive query patterns.

This module provides reusable query patterns that appear frequently
across service classes, reducing boilerplate code.
"""

from typing import Optional, List, Type, TypeVar
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import DeclarativeMeta

T = TypeVar('T', bound=DeclarativeMeta)


async def get_by_id(
    db: AsyncSession,
    model: Type[T],
    id_value: any,
    id_field: str = "id"
) -> Optional[T]:
    """Generic get by ID query.

    Args:
        db: Database session
        model: SQLAlchemy model class
        id_value: ID value to search for
        id_field: Name of ID field (default: "id")

    Returns:
        Model instance or None
    """
    stmt = select(model).where(getattr(model, id_field) == id_value)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_user_id(
    db: AsyncSession,
    model: Type[T],
    user_id: int,
    skip: int = 0,
    limit: int = 100,
    order_by: Optional[any] = None,
) -> List[T]:
    """Generic get by user_id with pagination.

    Args:
        db: Database session
        model: SQLAlchemy model class
        user_id: User ID to filter by
        skip: Number of records to skip
        limit: Maximum number of records
        order_by: Optional order by clause

    Returns:
        List of model instances
    """
    stmt = select(model).where(model.user_id == user_id)

    if order_by is not None:
        stmt = stmt.order_by(order_by)

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_top_by_field(
    db: AsyncSession,
    model: Type[T],
    user_id: int,
    field_name: str,
    limit: int = 10,
    ascending: bool = False,
) -> List[T]:
    """Get top records ordered by a specific field.

    Args:
        db: Database session
        model: SQLAlchemy model class
        user_id: User ID to filter by
        field_name: Name of field to order by
        limit: Maximum number of records
        ascending: If True, order ascending; else descending

    Returns:
        List of model instances
    """
    stmt = select(model).where(model.user_id == user_id)

    order_field = getattr(model, field_name)
    if ascending:
        stmt = stmt.order_by(order_field.asc())
    else:
        stmt = stmt.order_by(order_field.desc())

    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def count_by_condition(
    db: AsyncSession,
    model: Type[T],
    **filters
) -> int:
    """Count records matching given filters.

    Args:
        db: Database session
        model: SQLAlchemy model class
        **filters: Field name and value pairs to filter by

    Returns:
        Count of matching records
    """
    stmt = select(func.count(model.id))
    for field_name, value in filters.items():
        stmt = stmt.where(getattr(model, field_name) == value)

    result = await db.execute(stmt)
    return result.scalar_one() or 0


async def get_latest_by_field(
    db: AsyncSession,
    model: Type[T],
    user_id: int,
    date_field: str = "created_at",
) -> Optional[T]:
    """Get most recent record for a user.

    Args:
        db: Database session
        model: SQLAlchemy model class
        user_id: User ID to filter by
        date_field: Name of timestamp field (default: "created_at")

    Returns:
        Most recent model instance or None
    """
    stmt = (
        select(model)
        .where(model.user_id == user_id)
        .order_by(getattr(model, date_field).desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
