"""RStudio Server inside the secure processing environment (M-29, D-11; S-020, S-040, Art. 73).

The barrier is the container, not RStudio's settings: `--network none` means R code cannot send anything anywhere, and
the permit's DuckDB file is mounted read-only. The browser reaches RStudio over a Unix socket through a proxy that
refuses RStudio's file download routes (`docker/rstudio-proxy`). What a browser shows, its user can still copy, by hand
or from the browser's own traffic; only a locked-down remote desktop would change that.

shortcut: one session at a time on one port (a new permit's session ends the previous one), no RStudio login for a smooth
demo, so whoever reaches the port gets the session and the person is only the name in `?user=` (D-10, D-11); upgrade to a
port per session and real logins before any non-synthetic use.
"""

import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

IMAGE = os.environ.get("RSTUDIO_IMAGE", "hdab-rstudio:latest")  # `make spe-image`
PROXY_IMAGE = os.environ.get("RSTUDIO_PROXY_IMAGE", "hdab-rstudio-proxy:latest")
BIND = os.environ.get("RSTUDIO_BIND", "127.0.0.1")  # the tailnet demo sets its Tailscale address (scripts/demo.sh)
PORT = int(os.environ.get("RSTUDIO_PORT", "8787"))
URL = os.environ.get("RSTUDIO_URL", f"http://localhost:{PORT}")
NAME = os.environ.get("RSTUDIO_NAME", "hdab-rstudio")  # the tailnet demo has its own, so `make seed` here cannot end it
PROXY = f"{NAME}-proxy"
SOCKET_VOLUME = f"{NAME}-socket"
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")  # goes into a docker argument; request IDs come from outside


class Unavailable(RuntimeError):
    """Docker or the image is missing, or the session did not come up."""


def _docker(*args: str, check: bool = True) -> str:
    try:
        run = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Unavailable(f"Docker is not available: {e}") from e
    if check and run.returncode:
        raise Unavailable(run.stderr.strip())
    return run.stdout.strip()


def _current() -> tuple[str, bool] | None:
    """Request ID of the session container, and whether it runs. Survives a backend restart."""
    out = _docker("inspect", "-f", '{{index .Config.Labels "hdab.request"}} {{.State.Running}}', NAME, check=False)
    parts = out.split()
    return (parts[0], parts[1] == "true") if len(parts) == 2 else None


def _wait_ready(seconds: float = 30) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"http://{BIND}:{PORT}/", timeout=2).close()
            return
        except OSError:  # URLError and connection resets while RStudio starts
            time.sleep(0.5)
    raise Unavailable("RStudio did not start in time.")


def _remove() -> None:
    _docker("rm", "-f", NAME, PROXY, check=False)
    _docker("volume", "rm", "-f", SOCKET_VOLUME, check=False)  # a stale socket would stop RStudio from starting


def start(request_id: str, data: Path) -> dict:
    """Open the session for one permit, or return the one already running, so a second click loses no work."""
    if not SAFE_ID.fullmatch(request_id):
        raise Unavailable(f"Request ID {request_id!r} cannot be used for a session.")
    current = _current()
    if not (current and current[0] == request_id and current[1]):
        _remove()
        _docker("run", "-d", "--name", NAME, "--network", "none", "--memory", "4g", "--pids-limit", "512",
                "--label", f"hdab.request={request_id}", "-e", "DISABLE_AUTH=true",
                "--mount", f"type=bind,src={Path(data).resolve()},dst=/data/spe.duckdb,readonly",
                "--mount", f"type=volume,src={SOCKET_VOLUME},dst=/run/rstudio-socket", IMAGE)
        _docker("run", "-d", "--name", PROXY, "-p", f"{BIND}:{PORT}:8787",
                "--mount", f"type=volume,src={SOCKET_VOLUME},dst=/run/rstudio-socket", PROXY_IMAGE)
    try:
        _wait_ready()
    except Unavailable:
        _remove()
        raise
    return {"url": URL}


def stop(request_id: str) -> bool:
    """End this permit's session (S-076: a revoked permit must not keep working); True if there was one."""
    try:
        current = _current()
        if not current or current[0] != request_id:
            return False
        _remove()
        return True
    except Unavailable:  # no Docker, so no session either; must never block an override
        return False
