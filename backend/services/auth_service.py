from typing import Optional

from fastapi import HTTPException, status

from backend.core.security import get_password_hash, verify_password
from backend.database.models import User


def get_user_by_username(db, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def get_user_by_phone(db, phone: str) -> Optional[User]:
    return db.query(User).filter(User.phone == phone).first()


def create_user(db, username: str, password: str, phone: Optional[str] = None) -> User:
    existing = get_user_by_username(db, username)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")

    if phone:
        existing_phone = get_user_by_phone(db, phone)
        if existing_phone:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phone already exists")

    hashed = get_password_hash(password)
    user = User(
        username=username,
        phone=phone,
        password_hash=hashed,
        role="user",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db, username: str, password: str) -> Optional[User]:
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
