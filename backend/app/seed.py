"""Seed the initial admin user. Run: python -m app.seed"""
import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User


async def seed_admin(username: str = "admin", password: str = "admin"):
    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.username == username))
        if result.scalar_one_or_none():
            print(f"User '{username}' already exists, skipping.")
            return

        result = await db.execute(select(Role).where(Role.name == "admin"))
        role = result.scalar_one()

        pw_hash = await hash_password(password)
        user = User(username=username, password_hash=pw_hash, role_id=role.id)
        db.add(user)
        await db.commit()
        print(f"Admin user '{username}' created. Change the password immediately!")


if __name__ == "__main__":
    username = sys.argv[1] if len(sys.argv) > 1 else "admin"
    password = sys.argv[2] if len(sys.argv) > 2 else "admin"
    asyncio.run(seed_admin(username, password))
