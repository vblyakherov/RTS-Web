from dataclasses import dataclass, field
import logging

from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.models.user import UserRole


logger = logging.getLogger(__name__)
_SENSITIVE_LOG_KEYS = {"password", "bind_password", "token", "secret"}


@dataclass(frozen=True)
class LdapAuthenticatedUser:
    username: str
    role: UserRole
    full_name: str | None = None
    email: str | None = None
    groups: list[str] = field(default_factory=list)


def _safe_log_value(value) -> str:
    if isinstance(value, (list, tuple, set)):
        return "[" + ", ".join(str(item) for item in value) + "]"
    return str(value)


def _log_ldap_event(level: int, message: str, **fields) -> None:
    safe_fields = {
        key: value
        for key, value in fields.items()
        if key.lower() not in _SENSITIVE_LOG_KEYS and value is not None
    }
    suffix = " ".join(
        f"{key}={_safe_log_value(value)}"
        for key, value in sorted(safe_fields.items())
    )
    logger.log(level, "LDAP auth: %s%s", message, f" {suffix}" if suffix else "")


def _ldap_result_summary(connection) -> str | None:
    result = getattr(connection, "result", None)
    if not isinstance(result, dict):
        return None
    parts = []
    for key in ("result", "description", "message", "dn"):
        value = result.get(key)
        if value not in (None, ""):
            parts.append(f"{key}={value}")
    return "; ".join(parts) if parts else None


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
        _log_ldap_event(
            logging.ERROR,
            "configuration error",
            server_url_configured=bool(server_url),
            user_base_dn_configured=bool(user_base_dn),
        )
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
        _log_ldap_event(
            logging.WARNING,
            "empty username or password",
            username_present=bool(username),
            password_present=bool(password),
        )
        return None

    try:
        server_url, user_base_dn = _required_ldap_config()
    except RuntimeError:
        return None

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
    stage = "server_init"

    _log_ldap_event(
        logging.INFO,
        "start",
        username=username,
        server_url=server_url,
        search_base=user_base_dn,
        search_filter=search_filter,
        bind_mode="service" if bind_dn and bind_password else "direct",
    )

    try:
        server = Server(
            server_url,
            get_info=ALL,
            connect_timeout=settings.LDAP_CONNECT_TIMEOUT,
        )
        if bind_dn and bind_password:
            stage = "service_bind"
            _log_ldap_event(
                logging.INFO,
                "service bind attempt",
                username=username,
                bind_dn=bind_dn,
                server_url=server_url,
            )
            search_connection = Connection(
                server,
                user=bind_dn,
                password=bind_password,
                auto_bind=True,
                receive_timeout=settings.LDAP_CONNECT_TIMEOUT,
            )
            _log_ldap_event(
                logging.INFO,
                "service bind success",
                username=username,
                bind_dn=bind_dn,
            )
        else:
            stage = "direct_bind"
            direct_bind_user = _user_bind_name(username, None)
            _log_ldap_event(
                logging.INFO,
                "direct bind attempt",
                username=username,
                bind_user=direct_bind_user,
                server_url=server_url,
            )
            search_connection = Connection(
                server,
                user=direct_bind_user,
                password=password,
                auto_bind=True,
                receive_timeout=settings.LDAP_CONNECT_TIMEOUT,
            )
            _log_ldap_event(
                logging.INFO,
                "direct bind success",
                username=username,
                bind_user=direct_bind_user,
            )

        stage = "search"
        if not search_connection.search(
            search_base=user_base_dn,
            search_filter=search_filter,
            attributes=attributes,
            size_limit=1,
        ):
            _log_ldap_event(
                logging.WARNING,
                "search failed",
                username=username,
                search_base=user_base_dn,
                search_filter=search_filter,
                ldap_result=_ldap_result_summary(search_connection),
            )
            return None
        if not search_connection.entries:
            _log_ldap_event(
                logging.WARNING,
                "user not found",
                username=username,
                search_base=user_base_dn,
                search_filter=search_filter,
                ldap_result=_ldap_result_summary(search_connection),
            )
            return None

        entry = search_connection.entries[0]
        user_dn = entry.entry_dn
        groups = _entry_values(entry, settings.LDAP_GROUP_ATTRIBUTE)
        role = _role_from_groups(groups)
        if role is None:
            _log_ldap_event(
                logging.WARNING,
                "user has no authorized tracker group",
                username=username,
                user_dn=user_dn,
                group_count=len(groups),
                groups=groups,
                required_user_group=settings.LDAP_USERS_GROUP,
                required_admin_group=settings.LDAP_ADMINS_GROUP,
            )
            return None

        if bind_dn and bind_password:
            stage = "user_bind"
            user_bind_name = _user_bind_name(username, user_dn)
            _log_ldap_event(
                logging.INFO,
                "user bind attempt",
                username=username,
                user_dn=user_dn,
                bind_user=user_bind_name,
            )
            user_connection = Connection(
                server,
                user=user_bind_name,
                password=password,
                auto_bind=True,
                receive_timeout=settings.LDAP_CONNECT_TIMEOUT,
            )
            user_connection.unbind()
            _log_ldap_event(
                logging.INFO,
                "user bind success",
                username=username,
                user_dn=user_dn,
                bind_user=user_bind_name,
            )

        ldap_username = (
            _first_entry_value(entry, settings.LDAP_USERNAME_ATTRIBUTE) or username
        ).strip()
        _log_ldap_event(
            logging.INFO,
            "success",
            username=username,
            ldap_username=ldap_username,
            role=role.value,
            user_dn=user_dn,
            group_count=len(groups),
        )
        return LdapAuthenticatedUser(
            username=ldap_username,
            full_name=_first_entry_value(entry, settings.LDAP_FULL_NAME_ATTRIBUTE),
            email=_first_entry_value(entry, settings.LDAP_EMAIL_ATTRIBUTE),
            role=role,
            groups=groups,
        )
    except LDAPException as exc:
        _log_ldap_event(
            logging.WARNING,
            "LDAP exception",
            username=username,
            stage=stage,
            error_type=type(exc).__name__,
            error=str(exc),
            ldap_result=_ldap_result_summary(search_connection),
        )
        return None
    except Exception:
        logger.exception(
            "LDAP auth: unexpected exception username=%s stage=%s",
            username,
            stage,
        )
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
