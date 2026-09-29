"""I1 — the API and worker make no outbound network connection in demo or airgap mode.

`install()` wraps the socket layer: name resolution is refused for any host that is not explicitly allowed
(so not even a DNS query leaves), and connections or datagrams to a public address are refused. Loopback,
private (RFC 1918 / ULA) and link-local addresses stay reachable, which is where the database lives.
Unix sockets are never touched. `warn` mode logs instead of refusing (dev only).
"""

from __future__ import annotations

import ipaddress
import logging
import socket
import threading
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("sutradhar.offline_guard")

_ALWAYS_ALLOWED = frozenset({"localhost", "localhost.localdomain", "ip6-localhost"})
_INET = (socket.AF_INET, socket.AF_INET6)


class OfflineGuardError(PermissionError):
    """An outbound network operation was refused by the offline guard."""


@dataclass
class GuardState:
    mode: str = "off"
    allow_hosts: frozenset[str] = frozenset()
    blocked: int = 0
    last_blocked: list[str] = field(default_factory=list)
    originals: dict[str, Any] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)


_state = GuardState()


def _local_ip(host: str) -> bool | None:
    """True/False for an IP literal (local or not); None when `host` is a name."""
    try:
        ip = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_unspecified


def _host_allowed(host: str | bytes | None) -> bool:
    if host is None:
        return True  # getaddrinfo(None, port) resolves to local wildcard addresses
    text = host.decode() if isinstance(host, bytes) else host
    text = text.strip().rstrip(".").lower()
    local = _local_ip(text)
    if local is not None:
        return local
    return text in _ALWAYS_ALLOWED or text in _state.allow_hosts


def _refuse(what: str) -> None:
    with _state.lock:
        _state.blocked += 1
        _state.last_blocked = [*_state.last_blocked[-9:], what]
    if _state.mode == "warn":
        log.warning("offline guard (warn): allowing %s", what)
        return
    log.error("offline guard: blocked %s", what)
    raise OfflineGuardError(f"offline guard: outbound network access to {what} is blocked (I1)")


def _check_address(family: int, address: Any, verb: str) -> None:
    if family in _INET and isinstance(address, tuple) and address and not _host_allowed(address[0]):
        _refuse(f"{verb} {address[0]}:{address[1] if len(address) > 1 else '?'}")


def _guarded_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> Any:
    if not _host_allowed(host):
        _refuse(f"resolve {host!r}")
    return _state.originals["getaddrinfo"](host, port, *args, **kwargs)


def _guarded_connect(self: socket.socket, address: Any) -> Any:
    _check_address(self.family, address, "connect")
    return _state.originals["connect"](self, address)


def _guarded_connect_ex(self: socket.socket, address: Any) -> Any:
    _check_address(self.family, address, "connect")
    return _state.originals["connect_ex"](self, address)


def _guarded_sendto(self: socket.socket, data: Any, *args: Any) -> Any:
    if args:
        _check_address(self.family, args[-1], "send to")
    return _state.originals["sendto"](self, data, *args)


def install(mode: str, allow_hosts: Iterable[str | None] = ()) -> None:
    """Idempotent. `mode` is on | warn | off. `allow_hosts` are extra host names (e.g. the DB service)."""
    if mode not in ("on", "warn", "off"):
        raise ValueError(f"unknown offline guard mode {mode!r}")
    with _state.lock:
        _state.mode = mode
        _state.allow_hosts = frozenset(h.strip().lower() for h in allow_hosts if h)
        if mode == "off" or _state.originals:
            return
        _state.originals = {
            "getaddrinfo": socket.getaddrinfo,
            "connect": socket.socket.connect,
            "connect_ex": socket.socket.connect_ex,
            "sendto": socket.socket.sendto,
        }
        socket.getaddrinfo = _guarded_getaddrinfo  # type: ignore[assignment]
        socket.socket.connect = _guarded_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = _guarded_connect_ex  # type: ignore[method-assign]
        socket.socket.sendto = _guarded_sendto  # type: ignore[method-assign]


def uninstall() -> None:
    """Restore the socket layer (tests only)."""
    with _state.lock:
        if _state.originals:
            socket.getaddrinfo = _state.originals["getaddrinfo"]
            socket.socket.connect = _state.originals["connect"]  # type: ignore[method-assign]
            socket.socket.connect_ex = _state.originals["connect_ex"]  # type: ignore[method-assign]
            socket.socket.sendto = _state.originals["sendto"]  # type: ignore[method-assign]
        _state.originals = {}
        _state.mode = "off"
        _state.blocked = 0
        _state.last_blocked = []


def status() -> dict[str, Any]:
    with _state.lock:
        return {
            "mode": _state.mode,
            "active": bool(_state.originals),
            "blocked_attempts": _state.blocked,
            "allow_hosts": sorted(_state.allow_hosts),
        }
