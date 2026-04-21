#!/usr/bin/env python3
"""
Создание первого admin-пользователя.
Запуск: docker compose exec backend python create_admin.py
"""
import asyncio
import sys
from app.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.services.auth import get_password_hash


async def create_admin(username: str, email: str, password: str) -> None:
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        existing = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
        if existing:
            print(f"User '{username}' already exists.")
            return

        admin = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            full_name="Administrator",
            role=UserRole.admin,
        )
        db.add(admin)
        await db.commit()
        print(f"Admin user '{username}' created successfully.")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python create_admin.py <username> <email> <password>")
        sys.exit(1)
    asyncio.run(create_admin(sys.argv[1], sys.argv[2], sys.argv[3]))
