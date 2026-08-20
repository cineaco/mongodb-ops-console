from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User


async def create_user(
    db: AsyncSession,
    *,
    username: str,
    password: str,
    email: str | None = None,
    role_name: str,
) -> User:
    result = await db.execute(select(Role).where(Role.name == role_name))
    role = result.scalar_one()
    pw_hash = await hash_password(password)
    user = User(username=username, email=email, password_hash=pw_hash, role_id=role.id)
    db.add(user)
    await db.flush()
    return user


async def list_users(db: AsyncSession) -> list[User]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())


async def get_user(db: AsyncSession, user_id) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def update_user(
    db: AsyncSession,
    user: User,
    *,
    role_name: str | None = None,
    disabled: bool | None = None,
    password: str | None = None,
) -> User:
    if role_name is not None:
        result = await db.execute(select(Role).where(Role.name == role_name))
        role = result.scalar_one()
        user.role_id = role.id
    if disabled is not None:
        user.disabled = disabled
    if password is not None:
        user.password_hash = await hash_password(password)
    await db.flush()
    return user


async def delete_user(db: AsyncSession, user: User) -> None:
    await db.delete(user)
    await db.flush()
