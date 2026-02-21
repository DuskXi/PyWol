"""
WOL (Wake-on-LAN) core module.

Supports two sending methods, configurable via environment variable WOL_METHOD:
  - "auto"       (default) smart selection based on configuration:
                   • if WOL_INTERFACE is set → etherwake (Layer 2, most reliable)
                   • otherwise → UDP socket (same as wakeonlan)
  - "etherwake"  use etherwake only (Layer 2, Linux)
  - "socket"     use pure Python UDP broadcast (cross-platform)

Environment variables:
  WOL_METHOD    – sending method (auto / etherwake / socket)
  WOL_INTERFACE – network interface for etherwake, e.g. "eth0"

NOTE on etherwake:
  etherwake sends raw Ethernet frames (Layer 2). Without an explicit
  interface (-i), it picks the first non-loopback NIC it finds, which
  in Docker (even with network_mode: host) is often wrong (e.g. docker0,
  veth*, br-*). The command still exits 0, so failures are *silent*.
  → Always set WOL_INTERFACE when using etherwake.
  → In auto mode, etherwake is only used when WOL_INTERFACE is set.
"""

import asyncio
import os
import platform
import re
import shutil
import socket
import subprocess

from loguru import logger

# ── Configuration ────────────────────────────────────
WOL_METHOD: str = os.getenv("WOL_METHOD", "auto").lower()
WOL_INTERFACE: str = os.getenv("WOL_INTERFACE", "")


# ── Helpers ──────────────────────────────────────────
def _etherwake_available() -> bool:
    """Check if the etherwake command is available on this system."""
    return shutil.which("etherwake") is not None


def get_wol_info() -> dict:
    """Return current WOL configuration for diagnostics."""
    return {
        "method": WOL_METHOD,
        "interface": WOL_INTERFACE or "(default)",
        "etherwake_available": _etherwake_available(),
        "platform": platform.system(),
    }


# ── Magic Packet ─────────────────────────────────────
def create_magic_packet(mac_address: str) -> bytes:
    """Create a Wake-on-LAN magic packet (6×0xFF + 16×MAC)."""
    mac = re.sub(r"[^0-9A-Fa-f]", "", mac_address)
    if len(mac) != 12:
        raise ValueError(f"Invalid MAC address: {mac_address}")
    mac_bytes = bytes.fromhex(mac)
    return b"\xff" * 6 + mac_bytes * 16


# ── Sending Methods ─────────────────────────────────
def _send_via_socket(
    mac_address: str,
    broadcast: str = "255.255.255.255",
    port: int = 9,
) -> None:
    """Send WOL magic packet via UDP broadcast (Layer 3/4).

    This is the classic cross-platform approach. It works well when
    the sending host is on the same subnet as the target and broadcast
    is not filtered. In Docker it requires ``network_mode: host``.
    """
    packet = create_magic_packet(mac_address)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(packet, (broadcast, port))
    logger.info(f"[socket] WOL packet sent to {mac_address} via {broadcast}:{port}")


def _send_via_etherwake(mac_address: str) -> None:
    """Send WOL packet using etherwake (Layer 2 raw Ethernet frame).

    etherwake works at the data-link layer, which is more reliable
    than UDP broadcast on complex networks. It requires:
      - Linux with etherwake installed (``apt-get install etherwake``)
      - Root or CAP_NET_RAW capability
      - ``network_mode: host`` in Docker (to access host NICs)

    The network interface can be specified via the WOL_INTERFACE env var.
    """
    cmd = ["etherwake"]
    if WOL_INTERFACE:
        cmd.extend(["-i", WOL_INTERFACE])
    cmd.append(mac_address)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(
            f"etherwake failed (exit {result.returncode}): {stderr}"
        )
    iface_msg = f" via interface {WOL_INTERFACE}" if WOL_INTERFACE else ""
    logger.info(f"[etherwake] WOL packet sent to {mac_address}{iface_msg}")


# ── Public API ───────────────────────────────────────
def send_wol(
    mac_address: str,
    broadcast: str = "255.255.255.255",
    port: int = 9,
) -> bool:
    """Send a WOL magic packet using the configured method.

    The method is determined by the WOL_METHOD environment variable:
      - "auto"      – smart: etherwake (if WOL_INTERFACE set), else socket
      - "etherwake"  – etherwake only; raises if unavailable
      - "socket"     – pure Python UDP socket only

    Args:
        mac_address: Target MAC address (any common format).
        broadcast:   Broadcast address for socket method.
        port:        UDP port for socket method (default 9).

    Returns:
        True on success.

    Raises:
        RuntimeError / ValueError / OSError on failure.
    """
    try:
        if WOL_METHOD == "etherwake":
            if not _etherwake_available():
                raise RuntimeError(
                    "etherwake not found. "
                    "Install: apt-get install etherwake, "
                    "or set WOL_METHOD=auto to enable fallback."
                )
            if not WOL_INTERFACE:
                logger.warning(
                    "etherwake without WOL_INTERFACE may use the wrong NIC! "
                    "Set WOL_INTERFACE=<your_nic> (e.g. eth0) for reliable operation."
                )
            _send_via_etherwake(mac_address)

        elif WOL_METHOD == "socket":
            _send_via_socket(mac_address, broadcast, port)

        else:  # auto
            if WOL_INTERFACE and _etherwake_available():
                # WOL_INTERFACE is explicitly set → etherwake with correct NIC
                try:
                    _send_via_etherwake(mac_address)
                except Exception as e:
                    logger.warning(
                        f"etherwake failed ({e}), falling back to socket"
                    )
                    _send_via_socket(mac_address, broadcast, port)
            else:
                # No interface specified → use UDP socket (same as wakeonlan)
                # etherwake without -i is unreliable: it picks the first NIC
                # it finds, which in Docker is often wrong (docker0, veth*, etc.)
                if _etherwake_available() and not WOL_INTERFACE:
                    logger.debug(
                        "etherwake available but WOL_INTERFACE not set; "
                        "using socket method (UDP broadcast) for reliability. "
                        "Set WOL_INTERFACE=<nic> to use etherwake."
                    )
                _send_via_socket(mac_address, broadcast, port)

        return True
    except Exception:
        logger.error(f"Failed to send WOL packet to {mac_address}")
        raise


async def check_host_online(ip_address: str, timeout: int = 2) -> bool:
    """Check if a host is online by pinging it."""
    if not ip_address:
        return False
    try:
        if platform.system().lower() == "windows":
            cmd = ["ping", "-n", "1", "-w", str(timeout * 1000), ip_address]
        else:
            cmd = ["ping", "-c", "1", "-W", str(timeout), ip_address]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(process.wait(), timeout=timeout + 2)
        return process.returncode == 0
    except (asyncio.TimeoutError, Exception):
        return False
