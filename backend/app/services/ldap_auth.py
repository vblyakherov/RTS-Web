from dataclasses import dataclass, field
import logging
import socket
from urllib.parse import urlparse

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


def _ldap_server_urls() -> list[str]:
    raw_urls = _setting_value(settings.LDAP_SERVER_URLS) or _setting_value(settings.LDAP_SERVER_URL)
    if not raw_urls:
        return []
    return [url.strip() for url in raw_urls.split(",") if url.strip()]


def _ldap_auto_referrals() -> bool:
    return bool(settings.LDAP_AUTO_REFERRALS)


def _ldap_get_info() -> str:
    mode = settings.LDAP_GET_INFO.strip().lower()
    return "ALL" if mode == "all" else "NONE"


def _parse_ldap_server_url(server_url: str) -> tuple[str, int, bool]:
    normalized_url = server_url if "://" in server_url else f"ldap://{server_url}"
    parsed = urlparse(normalized_url)
    if parsed.scheme not in {"ldap", "ldaps"}:
        raise ValueError(f"Unsupported LDAP URL scheme: {parsed.scheme}")
    if not parsed.hostname:
        raise ValueError("LDAP server URL must include a host")
    port = parsed.port or (636 if parsed.scheme == "ldaps" else 389)
    return parsed.hostname, port, parsed.scheme == "ldaps"


def _connect_host(host: str, port: int) -> tuple[str, list[str]]:
    if not settings.LDAP_FORCE_IPV4:
        return host, []
    addresses = socket.getaddrinfo(
        host,
        port,
        family=socket.AF_INET,
        type=socket.SOCK_STREAM,
    )
    resolved = sorted({item[4][0] for item in addresses})
    if not resolved:
        raise OSError(f"No IPv4 address found for LDAP host {host}")
    return resolved[0], resolved


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


def _required_ldap_config() -> tuple[list[str], str]:
    server_urls = _ldap_server_urls()
    user_base_dn = _setting_value(settings.LDAP_USER_BASE_DN)
    if not server_urls or not user_base_dn:
        _log_ldap_event(
            logging.ERROR,
            "configuration error",
            server_url_configured=bool(server_urls),
            user_base_dn_configured=bool(user_base_dn),
        )
        raise RuntimeError("LDAP_SERVER_URL(S) and LDAP_USER_BASE_DN must be configured")
    return server_urls, user_base_dn


def _authenticate_ldap_user_on_server(
    username: str,
    password: str,
    server_url: str,
    user_base_dn: str,
    search_filter: str,
    attributes: list[str],
    bind_dn: str | None,
    bind_password: str | None,
) -> tuple[LdapAuthenticatedUser | None, bool]:
    from ldap3 import ALL, NONE, Connection, Server
    from ldap3.core.exceptions import LDAPException

    search_connection = None
    stage = "server_init"
    try:
        host, port, use_ssl = _parse_ldap_server_url(server_url)
        connect_host, resolved_ipv4 = _connect_host(host, port)
        get_info_mode = _ldap_get_info()

        _log_ldap_event(
            logging.INFO,
            "server attempt",
            username=username,
            server_url=server_url,
            host=host,
            port=port,
            use_ssl=use_ssl,
            connect_host=connect_host,
            force_ipv4=settings.LDAP_FORCE_IPV4,
            resolved_ipv4=resolved_ipv4,
            get_info=get_info_mode,
            auto_referrals=_ldap_auto_referrals(),
            search_base=user_base_dn,
            search_filter=search_filter,
            bind_mode="service" if bind_dn and bind_password else "direct",
        )

        server = Server(
            connect_host,
            port=port,
            use_ssl=use_ssl,
            get_info=ALL if get_info_mode == "ALL" else NONE,
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
                auto_referrals=_ldap_auto_referrals(),
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
                auto_referrals=_ldap_auto_referrals(),
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
            return None, False
        if not search_connection.entries:
            _log_ldap_event(
                logging.WARNING,
                "user not found",
                username=username,
                search_base=user_base_dn,
                search_filter=search_filter,
                ldap_result=_ldap_result_summary(search_connection),
            )
            return None, False

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
            return None, False

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
                auto_referrals=_ldap_auto_referrals(),
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
        ), False
    except LDAPException as exc:
        retry_next = "Socket" in type(exc).__name__ or "timed out" in str(exc).lower()
        _log_ldap_event(
            logging.WARNING,
            "LDAP exception",
            username=username,
            server_url=server_url,
            stage=stage,
            error_type=type(exc).__name__,
            error=str(exc),
            ldap_result=_ldap_result_summary(search_connection),
            retry_next_server=retry_next,
        )
        return None, retry_next
    except Exception as exc:
        logger.exception(
            "LDAP auth: unexpected exception username=%s server_url=%s stage=%s",
            username,
            server_url,
            stage,
        )
        return None, isinstance(exc, (OSError, ValueError))
    finally:
        if search_connection is not None and search_connection.bound:
            search_connection.unbind()


def _authenticate_ldap_user_blocking(
    username: str,
    password: str,
) -> LdapAuthenticatedUser | None:
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
        server_urls, user_base_dn = _required_ldap_config()
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

    _log_ldap_event(
        logging.INFO,
        "start",
        username=username,
        server_urls=server_urls,
        search_base=user_base_dn,
        search_filter=search_filter,
        bind_mode="service" if bind_dn and bind_password else "direct",
    )

    for server_url in server_urls:
        user, retry_next = _authenticate_ldap_user_on_server(
            username=username,
            password=password,
            server_url=server_url,
            user_base_dn=user_base_dn,
            search_filter=search_filter,
            attributes=attributes,
            bind_dn=bind_dn,
            bind_password=bind_password,
        )
        if user is not None:
            return user
        if not retry_next:
            return None

    _log_ldap_event(
        logging.WARNING,
        "all configured LDAP servers failed",
        username=username,
        server_urls=server_urls,
    )
    return None


async def authenticate_ldap_user(
    username: str,
    password: str,
) -> LdapAuthenticatedUser | None:
    return await run_in_threadpool(
        _authenticate_ldap_user_blocking,
        username,
        password,
    )
