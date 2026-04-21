from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings
from app.schemas.auth import TokenData

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS_TOKEN_TYPE = "access"
EXCEL_SYNC_TOKEN_TYPE = "excel_sync"


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(
    user_id: int,
    role: str,
    expires_delta: timedelta | None = None,
    *,
    token_type: str = ACCESS_TOKEN_TYPE,
    project_id: int | None = None,
    contractor_id: int | None = None,
) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
        "token_type": token_type,
    }
    if project_id is not None:
        payload["project_id"] = project_id
    if contractor_id is not None:
        payload["contractor_id"] = contractor_id
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _as_optional_int(value) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = int(payload.get("sub"))
        role = payload.get("role")
        token_type = payload.get("token_type") or ACCESS_TOKEN_TYPE
        project_id = _as_optional_int(payload.get("project_id"))
        contractor_id = _as_optional_int(payload.get("contractor_id"))
        return TokenData(
            user_id=user_id,
            role=role,
            token_type=token_type,
            project_id=project_id,
            contractor_id=contractor_id,
        )
    except (JWTError, ValueError, TypeError):
        return TokenData()
