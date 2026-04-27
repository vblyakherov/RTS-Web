from dataclasses import dataclass, field

from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.models.user import UserRole


@dataclass(frozen=True)
class LdapAuthenticatedUser:
    username: str
    role: UserRole
    full_name: str | None = None
    email: str | None = None
    groups: list[str] = field(default_factory=list)


def _setting_value(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _group_names(groups: list[str]) -> set[str]:
    names: set[str] = set()
    for group in groups:
        normalized = group.strip().lower()
        if not normalized:
            continue
        names.add(normalized)
        first_part = normalized.split(",", 1)[0]
        if first_part.startswith("cn="):
            names.add(first_part[3:])
    return names


def _role_from_groups(groups: list[str]) -> UserRole | None:
    names = _group_names(groups)
    admin_group = settings.LDAP_ADMINS_GROUP.strip().lower()
    user_group = settings.LDAP_USERS_GROUP.strip().lower()
    if admin_group in names:
        return UserRole.admin
    if user_group in names:
        return UserRole.manager
    return None


def _entry_values(entry, attribute: str) -> list[str]:
    value = getattr(entry, attribute, None)
    if value is None:
        return []
    raw = getattr(value, "value", None)
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        return [str(item) for item in raw if item is not None]
    return [str(raw)]


def _first_entry_value(entry, attribute: str) -> str | None:
    values = _entry_values(entry, attribute)
    return values[0] if values else None


def _user_bind_name(username: str, user_dn: str | None) -> str:
    template = _setting_value(settings.LDAP_USER_DN_TEMPLATE)
    if template:
        return template.format(username=username, user_dn=user_dn or "")
    return user_dn or username


def _required_ldap_config() -> tuple[str, str]:
    server_url = _setting_value(settings.LDAP_SERVER_URL)
    user_base_dn = _setting_value(settings.LDAP_USER_BASE_DN)
    if not server_url or not user_base_dn:
        raise RuntimeError("LDAP_SERVER_URL and LDAP_USER_BASE_DN must be configured")
    return server_url, user_base_dn


def _authenticate_ldap_user_blocking(
    username: str,
    password: str,
) -> LdapAuthenticatedUser | None:
    from ldap3 import ALL, Connection, Server
    from ldap3.core.exceptions import LDAPException
    from ldap3.utils.conv import escape_filter_chars

    username = username.strip()
    if not username or not password:
        return None

    server_url, user_base_dn = _required_ldap_config()
    server = Server(
        server_url,
        get_info=ALL,
        connect_timeout=settings.LDAP_CONNECT_TIMEOUT,
    )
    safe_username = escape_filter_chars(username)
    search_filter = settings.LDAP_USER_FILTER.format(username=safe_username)
    attributes = [
        settings.LDAP_USERNAME_ATTRIBUTE,
        settings.LDAP_FULL_NAME_ATTRIBUTE,
        settings.LDAP_EMAIL_ATTRIBUTE,
        settings.LDAP_GROUP_ATTRIBUTE,
    ]

    bind_dn = _setting_value(settings.LDAP_BIND_DN)
    bind_password = _setting_value(settings.LDAP_BIND_PASSWORD)
    search_connection = None

    try:
        if bind_dn and bind_password:
            search_connection = Connection(
                server,
                user=bind_dn,
                password=bind_password,
                auto_bind=True,
                receive_timeout=settings.LDAP_CONNECT_TIMEOUT,
            )
        else:
            search_connection = Connection(
                server,
                user=_user_bind_name(username, None),
                password=password,
                auto_bind=True,
                receive_timeout=settings.LDAP_CONNECT_TIMEOUT,
            )

        if not search_connection.search(
            search_base=user_base_dn,
            search_filter=search_filter,
            attributes=attributes,
            size_limit=1,
        ):
            return None
        if not search_connection.entries:
            return None

        entry = search_connection.entries[0]
        user_dn = entry.entry_dn
        groups = _entry_values(entry, settings.LDAP_GROUP_ATTRIBUTE)
        role = _role_from_groups(groups)
        if role is None:
            return None

        if bind_dn and bind_password:
            user_connection = Connection(
                server,
                user=_user_bind_name(username, user_dn),
                password=password,
                auto_bind=True,
                receive_timeout=settings.LDAP_CONNECT_TIMEOUT,
            )
            user_connection.unbind()

        ldap_username = (
            _first_entry_value(entry, settings.LDAP_USERNAME_ATTRIBUTE) or username
        ).strip()
        return LdapAuthenticatedUser(
            username=ldap_username,
            full_name=_first_entry_value(entry, settings.LDAP_FULL_NAME_ATTRIBUTE),
            email=_first_entry_value(entry, settings.LDAP_EMAIL_ATTRIBUTE),
            role=role,
            groups=groups,
        )
    except LDAPException:
        return None
    finally:
        if search_connection is not None and search_connection.bound:
            search_connection.unbind()


async def authenticate_ldap_user(
    username: str,
    password: str,
) -> LdapAuthenticatedUser | None:
    return await run_in_threadpool(
        _authenticate_ldap_user_blocking,
        username,
        password,
    )
