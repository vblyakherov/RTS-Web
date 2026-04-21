from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: int | None = None
    role: str | None = None
    token_type: str | None = None
    project_id: int | None = None
    contractor_id: int | None = None


class LoginRequest(BaseModel):
    username: str
    password: str
