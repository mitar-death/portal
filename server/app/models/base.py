from datetime import datetime, timezone
from typing import Any, Optional, Sequence, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped

from server.app.core.databases import db_context

T = TypeVar("T", bound="BaseMixin")


class BaseMixin:
    """Base mixin providing async ORM helpers using a context-local DB session."""

    id: Mapped[Any]  # Should be overridden in child models with actual primary key type

    @classmethod
    def _get_db(cls) -> AsyncSession:
        """Get the current request-scoped async DB session from the context."""
        return db_context.get()

    @classmethod
    def _soft_delete_filter(cls: Type[T]):
        """Return a filter condition for non-deleted records if model has `deleted_at`."""
        if hasattr(cls, "deleted_at"):
            return getattr(cls, "deleted_at") is None  # noqa: E711
        return True

    @classmethod
    async def find(cls: Type[T], record_id: Any) -> Optional[T]:
        """Fetch a single record by its primary key, skipping soft-deleted ones."""
        db = cls._get_db()
        stmt = select(cls).where(cls.id == record_id, cls._soft_delete_filter())
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def all(cls: Type[T]) -> Sequence[T]:
        """Fetch all non-deleted records."""
        db = cls._get_db()
        stmt = select(cls).where(cls._soft_delete_filter())
        result = await db.execute(stmt)
        return result.scalars().all()

    @classmethod
    async def filter_by(cls: Type[T], **kwargs) -> Sequence[T]:
        """Filter records by given keyword arguments (soft delete aware)."""
        db = cls._get_db()
        stmt = select(cls).filter_by(**kwargs).where(cls._soft_delete_filter())
        result = await db.execute(stmt)
        return result.scalars().all()

    @classmethod
    async def first(cls: Type[T], **kwargs) -> Optional[T]:
        """Return the first matching record or None (soft delete aware)."""
        db = cls._get_db()
        stmt = select(cls).filter_by(**kwargs).where(cls._soft_delete_filter())
        result = await db.execute(stmt)
        return result.scalars().first()

    @classmethod
    async def get_from_user(cls: Type[T], user: T) -> Optional[T]:
        return await cls.first(user_id=user.id)

    async def save(self) -> None:
        """Add the instance to the DB session, commit, and refresh."""

        now = datetime.now(timezone.utc)

        if hasattr(self, "created_at") and getattr(self, "created_at") is None:
            setattr(self, "created_at", now)

        if hasattr(self, "updated_at") and getattr(self, "updated_at") is None:
            setattr(self, "updated_at", now)

        db = self._get_db()
        db.add(self)
        await db.commit()
        await db.refresh(self)

    async def _update_or_merge(self, use_merge: bool = False, **kwargs) -> T:
        """
        Internal helper to update fields and either add or merge the instance.

        Args:
            use_merge (bool): Whether to use merge instead of add.
            **kwargs: Fields to update.

        Returns:
            The updated and refreshed instance (self or merged).
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        if hasattr(self, "updated_at"):
            setattr(self, "updated_at", datetime.now(timezone.utc))

        db = self._get_db()
        instance = await db.merge(self) if use_merge else self
        if not use_merge:
            # fuck sqlachemy on this one,
            # why use same name for add and update
            # Fucking confusing
            db.add(instance)

        await db.commit()
        await db.refresh(instance)
        return instance

    async def update(self, **kwargs) -> None:
        """Update fields on the model, set updated_at, commit, and refresh."""
        await self._update_or_merge(use_merge=False, **kwargs)

    async def merge(self, **kwargs) -> T:
        """
        Merge the field into the database and return the database contentas well
        Returns a new model
        """
        return await self._update_or_merge(use_merge=True, **kwargs)

    async def delete(self) -> None:
        """Delete the instance from the DB session and commit."""
        db = self._get_db()
        if hasattr(self, "deleted_at"):
            self.deleted_at = datetime.now(timezone.utc)
            db.add(self)
        else:
            await db.delete(self)
        await db.commit()


class BaseModel(BaseMixin, DeclarativeBase):
    """Base model class to be inherited by all ORM models."""


async def table_migration(engine: AsyncEngine):
    """Create tables in the database using the async engine."""
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.create_all)
