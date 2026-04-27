from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    EXCEL_EXPORT_TOKEN_EXPIRE_MINUTES: int = 10080

    # App
    APP_ENV: str = "production"
    ALLOWED_ORIGINS: str = "http://localhost"

    # Auth
    # Supported values: "local", "ldap".
    AUTH_BACKEND: str = "local"

    # LDAP / Active Directory
    LDAP_SERVER_URL: str | None = None
    LDAP_BIND_DN: str | None = None
    LDAP_BIND_PASSWORD: str | None = None
    LDAP_USER_BASE_DN: str | None = None
    LDAP_USER_FILTER: str = "(&(objectClass=user)(sAMAccountName={username}))"
    LDAP_USER_DN_TEMPLATE: str | None = None
    LDAP_USERNAME_ATTRIBUTE: str = "sAMAccountName"
    LDAP_FULL_NAME_ATTRIBUTE: str = "displayName"
    LDAP_EMAIL_ATTRIBUTE: str = "mail"
    LDAP_GROUP_ATTRIBUTE: str = "memberOf"
    LDAP_USERS_GROUP: str = "tracker_users"
    LDAP_ADMINS_GROUP: str = "tracker_admins"
    LDAP_DEFAULT_EMAIL_DOMAIN: str = "ldap.local"
    LDAP_CONNECT_TIMEOUT: int = 5

    @property
    def origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
