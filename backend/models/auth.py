from pydantic import BaseModel, ConfigDict
from typing import Optional

class RegisterRequest(BaseModel):
    username: str
    phone: Optional[str] = None
    password: str

# 登录请求体
class LoginRequest(BaseModel):
    username: str
    password: str

# 用户响应模型（🔥 修复核心：添加 model_config）
class UserResponse(BaseModel):
    id: int
    username: str
    phone: str
    role: str
    is_active: bool

    # Pydantic v2 必须加这个配置
    model_config = ConfigDict(from_attributes=True)

# 登录返回 Token
class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

    model_config = ConfigDict(from_attributes=True)