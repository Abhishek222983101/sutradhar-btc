"""I1 — no outbound network access in demo or airgap mode; local services stay reachable."""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator

import pytest

from sutradhar_api import offline_guard
from sutradhar_api.offline_guard import OfflineGuardError


@pytest.fixture
def guard() -> Iterator[None]:
    before = offline_guard.status()
    offline_guard.uninstall()
    offline_guard.install("on", ["db"])
    yield
    offline_guard.uninstall()
    if before["active"]:
        offline_guard.install(before["mode"], before["allow_hosts"])


@pytest.mark.security
@pytest.mark.usefixtures("guard")
@pytest.mark.parametrize("address", [("1.1.1.1", 443), ("8.8.8.8", 53), ("2606:4700:4700::1111", 443)])
def test_offline_guard_blocks_public(address: tuple[str, int]) -> None:
    family = socket.AF_INET6 if ":" in address[0] else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as sock, pytest.raises(OfflineGuardError):
        sock.connect(address)
    assert offline_guard.status()["blocked_attempts"] >= 1


@pytest.mark.security
@pytest.mark.usefixtures("guard")
@pytest.mark.parametrize("host", ["example.com", "api.github.com", "pypi.org."])
def test_offline_guard_blocks_name_resolution(host: str) -> None:
    with pytest.raises(OfflineGuardError):
        socket.getaddrinfo(host, 443)
    with pytest.raises(OfflineGuardError):
        socket.create_connection((host, 443), timeout=1)


@pytest.mark.security
@pytest.mark.usefixtures("guard")
def test_offline_guard_blocks_udp_and_mapped_addresses() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp, pytest.raises(OfflineGuardError):
        udp.sendto(b"x", ("9.9.9.9", 53))
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock, pytest.raises(OfflineGuardError):
        sock.connect(("::ffff:1.1.1.1", 443))


@pytest.mark.usefixtures("guard")
def test_offline_guard_allows_loopback_and_allowed_hosts() -> None:
    server = socket.create_server(("127.0.0.1", 0))
    port = server.getsockname()[1]
    accepted = threading.Thread(target=lambda: server.accept()[0].close())
    accepted.start()
    with socket.create_connection(("localhost", port), timeout=2):
        pass
    accepted.join(2)
    server.close()
    assert offline_guard._host_allowed("db")
    assert offline_guard._host_allowed("10.0.0.5")
    assert offline_guard._host_allowed("172.18.0.2")
    assert not offline_guard._host_allowed("db.example.com")


def test_warn_mode_allows_but_counts() -> None:
    offline_guard.uninstall()
    offline_guard.install("warn")
    try:
        offline_guard._check_address(socket.AF_INET, ("1.1.1.1", 443), "connect")
        assert offline_guard.status()["blocked_attempts"] == 1
    finally:
        offline_guard.uninstall()


def test_app_reports_guard_status(client) -> None:  # type: ignore[no-untyped-def]
    info = client.get("/api/v1/system/info").json()
    assert info["offline_guard"]["mode"] == "on"
    assert info["offline_guard"]["active"] is True
