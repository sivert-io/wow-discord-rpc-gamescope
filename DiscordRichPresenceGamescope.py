#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import sys
import types
from pathlib import Path

# Native helper dependencies:
#   pillow pypresence python-xlib
from PIL import Image
from Xlib import X, display

HERE = Path(__file__).resolve().parent
UPSTREAM = HERE / "DiscordRichPresence.py"

DEFAULT_XDISPLAY = ":1"
DEFAULT_XAUTHORITY = "/run/pressure-vessel/Xauthority"

if not UPSTREAM.is_file():
    raise SystemExit(
        f"Missing upstream helper: {UPSTREAM}\n"
        "Place this file in CraftPresence/Script next to DiscordRichPresence.py."
    )

# Current upstream imports PyWinCtl even though this wrapper replaces its
# window-management/capture code. Stub it for a clean native Linux import.
sys.modules.setdefault("pywinctl", types.ModuleType("pywinctl"))
sys.path.insert(0, str(HERE))

spec = importlib.util.spec_from_file_location("craftpresence_upstream", UPSTREAM)
if spec is None or spec.loader is None:
    raise SystemExit("Could not load DiscordRichPresence.py")

cp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cp)

_last_x11_environment: tuple[str, str | None] | None = None


def _read_process_environment(pid: int) -> dict[str, str]:
    """Read a same-user Linux process environment from /proc."""
    try:
        raw = Path(f"/proc/{pid}/environ").read_bytes()
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return {}

    result: dict[str, str] = {}
    for entry in raw.split(b"\0"):
        if not entry or b"=" not in entry:
            continue
        key, value = entry.split(b"=", 1)
        result[key.decode(errors="replace")] = value.decode(errors="replace")
    return result


def detect_wow_x11_environment() -> tuple[str | None, str | None]:
    """Find the most likely WoW/Proton DISPLAY and XAUTHORITY under /proc."""
    proc = Path("/proc")
    try:
        entries = list(proc.iterdir())
    except OSError:
        return None, None

    candidates: list[tuple[int, str, str | None]] = []

    for entry in entries:
        if not entry.name.isdigit():
            continue

        try:
            cmdline = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                errors="replace"
            )
        except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
            continue

        if "wow.exe" not in cmdline.casefold():
            continue

        env = _read_process_environment(int(entry.name))
        xdisplay = env.get("DISPLAY")
        if not xdisplay:
            continue
        xauthority = env.get("XAUTHORITY")

        try:
            comm = (entry / "comm").read_text(errors="replace").strip().casefold()
        except OSError:
            comm = ""

        score = 0
        if comm == "wow.exe":
            score += 10
        if env.get("STEAM_COMPAT_DATA_PATH"):
            score += 5
        if env.get("WINEPREFIX"):
            score += 4
        if xauthority:
            score += 2
        if xauthority and "pressure-vessel" in xauthority:
            score += 5

        folded_cmd = cmdline.casefold()
        if "gamescope" in folded_cmd and "wine" not in folded_cmd:
            score -= 5
        if "umu-run" in folded_cmd and "wine" not in folded_cmd:
            score -= 2

        candidates.append((score, xdisplay, xauthority))

    if not candidates:
        return None, None

    candidates.sort(key=lambda item: item[0], reverse=True)
    _, xdisplay, xauthority = candidates[0]
    return xdisplay, xauthority


def resolve_x11_environment() -> tuple[str, str | None]:
    """
    Resolve the Gamescope X11 connection.

    Explicit CRAFTPRESENCE_* variables win. Otherwise, inspect Wow.exe every
    time so a user service can start before the game/Gamescope exist.
    """
    explicit_display = os.environ.get("CRAFTPRESENCE_XDISPLAY")
    explicit_xauthority = os.environ.get("CRAFTPRESENCE_XAUTHORITY")

    detected_display = None
    detected_xauthority = None
    if not explicit_display or not explicit_xauthority:
        detected_display, detected_xauthority = detect_wow_x11_environment()

    xdisplay = explicit_display or detected_display or DEFAULT_XDISPLAY
    xauthority = (
        explicit_xauthority or detected_xauthority or DEFAULT_XAUTHORITY
    )

    os.environ["DISPLAY"] = xdisplay
    if xauthority and Path(xauthority).exists():
        os.environ["XAUTHORITY"] = xauthority

    global _last_x11_environment
    current = (xdisplay, xauthority)
    if current != _last_x11_environment and hasattr(cp, "root_logger"):
        cp.root_logger.info(
            "Using Gamescope X11 display %s%s",
            xdisplay,
            f" with Xauthority {xauthority}" if xauthority else "",
        )
        _last_x11_environment = current

    return xdisplay, xauthority


def open_display():
    """Open the currently resolved Gamescope X11 display."""
    xdisplay, _ = resolve_x11_environment()
    return display.Display(xdisplay)


def iter_windows(root):
    """Depth-first traversal of the X11 window tree."""
    yield root
    try:
        children = root.query_tree().children
    except Exception:
        return
    for child in children:
        yield from iter_windows(child)


def find_x11_window(window_title: str):
    """Return (Display, Window) for the WoW window, or (None, None)."""
    dpy = None
    try:
        dpy = open_display()
        wanted = window_title.casefold()
        fallback = None

        for window in iter_windows(dpy.screen().root):
            try:
                name = window.get_wm_name()
            except Exception:
                continue
            if not name:
                continue

            title = str(name)
            folded = title.casefold()
            if folded == wanted:
                return dpy, window
            if wanted in folded and fallback is None:
                fallback = window

        if fallback is not None:
            return dpy, fallback
    except Exception:
        pass

    if dpy is not None:
        try:
            dpy.close()
        except Exception:
            pass
    return None, None


def is_running(window_title: str) -> bool:
    dpy, window = find_x11_window(window_title)
    found = window is not None
    if dpy is not None:
        try:
            dpy.close()
        except Exception:
            pass
    return found


def capture_top_rows(window_title: str, rows: int = 24) -> Image.Image | None:
    """Capture the top rows of the real WoW X11 window, before compositor scaling."""
    dpy, window = find_x11_window(window_title)
    if dpy is None or window is None:
        return None

    try:
        geometry = window.get_geometry()
        width = int(geometry.width)
        height = min(int(geometry.height), int(rows))
        if width <= 0 or height <= 0:
            return None

        shot = window.get_image(0, 0, width, height, X.ZPixmap, 0xFFFFFFFF)
        if shot is None:
            return None

        return Image.frombuffer(
            "RGB",
            (width, height),
            shot.data,
            "raw",
            "BGRX",
            0,
            1,
        ).copy()
    except Exception as exc:
        if hasattr(cp, "root_logger"):
            cp.root_logger.debug("Direct X11 capture failed: %s", exc)
        return None
    finally:
        try:
            dpy.close()
        except Exception:
            pass


def decode_row(im: Image.Image, y: int, minimum_run: int) -> str:
    """Collapse stable framebuffer-color runs into CraftPresence RGB triplets."""
    if im.width <= 0 or y < 0 or y >= im.height:
        return ""

    runs: list[tuple[tuple[int, int, int], int]] = []
    start = 0
    last = im.getpixel((0, y))

    for x in range(1, im.width):
        current = im.getpixel((x, y))
        if current != last:
            runs.append((last, x - start))
            last = current
            start = x
    runs.append((last, im.width - start))

    data: list[int] = []
    for rgb, run_length in runs:
        if run_length < minimum_run:
            continue

        # CraftPresence uses pure white as the end-of-message sentinel.
        if rgb == (255, 255, 255):
            break

        # Pure black separates adjacent identical encoded RGB triplets.
        if rgb == (0, 0, 0):
            continue

        data.extend(rgb)

    return cp.decode_read_data(data)


def payload_is_sane(
    decoded: str,
    event_length: int,
    event_key: str,
    array_separator_key: str,
) -> bool:
    """Reject blended rows that happen to satisfy the delimiter structure."""
    if not cp.verify_read_data(decoded, event_length, event_key, array_separator_key):
        return False

    parts = cp.get_decoded_chunks(decoded, event_key, array_separator_key)
    if len(parts) != event_length:
        return False

    # Discord application/client IDs are decimal snowflakes. Keep this broad
    # enough for other valid apps while still rejecting blended false positives.
    client_id = parts[0]
    if not client_id.isdigit() or not 15 <= len(client_id) <= 25:
        return False

    # Reject control characters introduced by sampling a transition row.
    for part in parts:
        if any(ord(ch) < 32 and ch not in "\t\r\n" for ch in part):
            return False

    return True


def decode_capture(
    im: Image.Image,
    event_length: int,
    event_key: str,
    array_separator_key: str,
):
    """Try clean interior rows first and return the first sane payload."""
    max_rows = min(im.height, 24)

    preferred = [y for y in (5, 4, 6, 7, 3, 2, 8, 9) if y < max_rows]
    row_order = preferred + [y for y in range(max_rows) if y not in preferred]

    for minimum_run in (4, 3, 5, 2, 6, 7, 8, 9, 10):
        for y in row_order:
            decoded = decode_row(im, y, minimum_run)
            if payload_is_sane(decoded, event_length, event_key, array_separator_key):
                return decoded, y, minimum_run

    return "", None, None


def read_squares(
    hwnd=None,
    event_length=0,
    event_key="",
    array_separator_key="",
    debug_mode=False,
):
    im = capture_top_rows(cp.config["process_name"], rows=24)
    if im is None:
        return None

    decoded, row, minimum_run = decode_capture(
        im, event_length, event_key, array_separator_key
    )

    if debug_mode:
        debug_path = HERE / "debug-gamescope-x11.png"
        im.save(debug_path)
        cp.root_logger.info("Saved raw Gamescope X11 capture to %s", debug_path)
        if decoded:
            cp.root_logger.info(
                "Decoded valid payload from row %s with minimum run %s: %s",
                row,
                minimum_run,
                decoded,
            )
        else:
            cp.root_logger.error(
                "Captured WoW, but no valid CraftPresence payload was decoded."
            )
        return None

    if not decoded:
        return None

    return cp.get_decoded_chunks(decoded, event_key, array_separator_key)


# Bypass upstream's Linux/Wayland refusal while preserving its payload parsing
# and Discord RPC behavior.
cp.is_windows = False
cp.is_linux = False
cp.is_running = is_running
cp.read_squares = read_squares

cp.config = cp.load_config()
cp.root_logger = cp.setup_logging(cp.config, cp.config["debug"])
cp.root_logger.info(
    "Gamescope X11 capture enabled; waiting for %s", cp.config["process_name"]
)
cp.main(cp.config["debug"])
