from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status

from backend.core import config
from backend.core.security import create_access_token, get_current_user
from backend.database.session import get_db
from backend.models.auth import RegisterRequest, LoginRequest, UserResponse, TokenResponse
from backend.services.auth_service import create_user, authenticate_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse)
def register(request: RegisterRequest, db=Depends(get_db)) -> UserResponse:
    user = create_user(db, username=request.username, password=request.password, phone=request.phone)
    # 🔥 修复：from_orm → model_validate
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db=Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, username=request.username, password=request.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token_expires = timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username, "type": "access"}, expires_delta=access_token_expires)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        # 🔥 修复：from_orm → model_validate
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def me(current_user=Depends(get_current_user)) -> UserResponse:
    # 🔥 修复：from_orm → model_validate
    return UserResponse.model_validate(current_user)