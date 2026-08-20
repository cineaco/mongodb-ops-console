import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.crypto import encrypt
from app.models.secret import Secret


async def create_secret(db, *, name, type, plaintext, created_by):
    ciphertext, nonce, auth_tag = encrypt(plaintext.encode("utf-8"))
    secret = Secret(name=name, type=type, ciphertext=ciphertext, nonce=nonce, auth_tag=auth_tag, created_by=created_by)
    db.add(secret)
    await db.flush()
    return secret


async def list_secrets(db):
    result = await db.execute(select(Secret).order_by(Secret.created_at.desc()))
    return list(result.scalars().all())


async def get_secret(db, secret_id):
    result = await db.execute(select(Secret).where(Secret.id == secret_id))
    return result.scalar_one_or_none()


async def delete_secret(db, secret):
    await db.delete(secret)
    await db.flush()
