"""SQLAlchemy implementation of user repository."""
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Platform
from app.models.database import User
from app.repositories.interfaces.user_repository import UserRepository


logger = structlog.get_logger()


class SQLAlchemyUserRepository(UserRepository):
    """SQLAlchemy implementation of user repository."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def create(self, entity: User) -> User | None:
        """Create a new user entity."""
        try:
            async with self.session_factory() as session:
                session.add(entity)
                await session.commit()
                await session.refresh(entity)
                return entity
        except Exception as e:
            logger.error("Error creating user", error=str(e))
            return None

    async def get_by_id(self, user_id: str) -> User | None:
        """Retrieve user by ID."""
        try:
            async with self.session_factory() as session:
                stmt = select(User).where(User.id == user_id)
                result = await session.execute(stmt)
                return result.scalars().first()
        except Exception as e:
            logger.error("Error retrieving user by ID", error=str(e), user_id=user_id)
            return None

    async def update(self, entity: User) -> User | None:
        """Update an existing user."""
        try:
            async with self.session_factory() as session:
                entity.updated_at = datetime.utcnow()
                await session.merge(entity)
                await session.commit()
                await session.refresh(entity)
                return entity
        except Exception as e:
            logger.error("Error updating user", error=str(e), user_id=entity.id)
            return None

    async def delete(self, user_id: str) -> bool:
        """Delete a user by ID."""
        try:
            async with self.session_factory() as session:
                stmt = select(User).where(User.id == user_id)
                result = await session.execute(stmt)
                user = result.scalars().first()
                if user:
                    await session.delete(user)
                    await session.commit()
                    return True
                return False
        except Exception as e:
            logger.error("Error deleting user", error=str(e), user_id=user_id)
            return False

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[User]:
        """List all users with pagination."""
        try:
            async with self.session_factory() as session:
                stmt = select(User).limit(limit).offset(offset)
                result = await session.execute(stmt)
                return list(result.scalars().all())
        except Exception as e:
            logger.error("Error listing users", error=str(e))
            return []

    async def exists(self, user_id: str) -> bool:
        """Check if user exists."""
        try:
            async with self.session_factory() as session:
                stmt = select(User.id).where(User.id == user_id)
                result = await session.execute(stmt)
                return result.scalar() is not None
        except Exception as e:
            logger.error("Error checking user existence", error=str(e), user_id=user_id)
            return False

    async def count(self) -> int:
        """Count total number of users."""
        try:
            async with self.session_factory() as session:
                stmt = select(User)
                result = await session.execute(stmt)
                return len(list(result.scalars().all()))
        except Exception as e:
            logger.error("Error counting users", error=str(e))
            return 0

    async def get_by_external_id(self, external_id: str, platform: Platform) -> User | None:
        """Retrieve user by external ID and platform."""
        try:
            async with self.session_factory() as session:
                stmt = select(User).where(
                    User.external_id == external_id,
                    User.platform == platform.value
                )
                result = await session.execute(stmt)
                return result.scalars().first()
        except Exception as e:
            logger.error("Error retrieving user by external ID", error=str(e), external_id=external_id)
            return None

    async def get_or_create_user(
        self,
        external_id: str,
        platform: Platform,
        metadata: dict[str, Any] | None = None
    ) -> User | None:
        """Get existing user or create new one."""
        try:
            async with self.session_factory() as session:
                # Try to find existing user
                stmt = select(User).where(
                    User.external_id == external_id,
                    User.platform == platform.value
                )
                result = await session.execute(stmt)
                user = result.scalars().first()

                if user:
                    # Update metadata if provided and different
                    if metadata and metadata != user.metadata:
                        user.metadata = metadata
                        user.updated_at = datetime.utcnow()
                        await session.commit()
                    return user

                # Create new user
                user = User(
                    external_id=external_id,
                    platform=platform.value,
                    metadata=metadata or {},
                    preferences={}
                )

                session.add(user)
                await session.commit()
                await session.refresh(user)

                logger.info("Created new user", user_id=user.id, platform=platform.value)
                return user

        except Exception as e:
            logger.error("Error getting/creating user", error=str(e), external_id=external_id)
            return None

    async def update_metadata(self, user_id: str, metadata: dict[str, Any]) -> User | None:
        """Update user metadata."""
        try:
            async with self.session_factory() as session:
                stmt = select(User).where(User.id == user_id)
                result = await session.execute(stmt)
                user = result.scalars().first()

                if user:
                    user.metadata = metadata
                    user.updated_at = datetime.utcnow()
                    await session.commit()
                    await session.refresh(user)
                    return user

                return None
        except Exception as e:
            logger.error("Error updating user metadata", error=str(e), user_id=user_id)
            return None

    async def update_preferences(self, user_id: str, preferences: dict[str, Any]) -> User | None:
        """Update user preferences."""
        try:
            async with self.session_factory() as session:
                stmt = select(User).where(User.id == user_id)
                result = await session.execute(stmt)
                user = result.scalars().first()

                if user:
                    user.preferences = preferences
                    user.updated_at = datetime.utcnow()
                    await session.commit()
                    await session.refresh(user)
                    return user

                return None
        except Exception as e:
            logger.error("Error updating user preferences", error=str(e), user_id=user_id)
            return None

    async def get_active_users(self, limit: int = 100) -> list[User]:
        """Get list of active users."""
        try:
            async with self.session_factory() as session:
                stmt = select(User).where(User.is_active == True).limit(limit)
                result = await session.execute(stmt)
                return list(result.scalars().all())
        except Exception as e:
            logger.error("Error retrieving active users", error=str(e))
            return []

    async def deactivate_user(self, user_id: str) -> bool:
        """Deactivate a user account."""
        try:
            async with self.session_factory() as session:
                stmt = select(User).where(User.id == user_id)
                result = await session.execute(stmt)
                user = result.scalars().first()

                if user:
                    user.is_active = False
                    user.updated_at = datetime.utcnow()
                    await session.commit()
                    return True

                return False
        except Exception as e:
            logger.error("Error deactivating user", error=str(e), user_id=user_id)
            return False