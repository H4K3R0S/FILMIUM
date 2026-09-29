"""mpv plejer — koristi sistemski mpv (Linux/Kali: apt `mpv`) ili portable mpv.exe (Windows, u bin/).

Samostalan plejer (jedan .exe, bez instalacije) koji CORE domeni (npr.
FILMIUM) koriste za reprodukciju bilo kog kodeka. Video se ugradjuje U
prozor aplikacije preko ``--wid`` (Window handle) + ``--geometry`` (pozicija),
a kontroliše preko mpv JSON IPC-a (imenovani pajp na Windowsu).
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from core.foundation.paths import core_paths

_IS_WIN = sys.platform.startswith("win")
# IPC kanal: Windows imenovani pajp; Linux/mac Unix socket u temp folderu.
_PIPE_NAME = r"\\.\pipe\core-mpv" if _IS_WIN else os.path.join(tempfile.gettempdir(), "core-mpv.sock")
_WINDOW_TITLE = "CORE-MPV-OVERLAY"

# Poddirektorijumi (relativno uz video) u kojima mpv traži prevode.
_SUBTITLE_DIR_NAMES = (
    "subs",
    "subtitles",
    "subtitle",
    "titl",
    "titlovi",
    "prevod",
    "prevodi",
)


def build_sub_file_paths(video_path: Path) -> str:
    """Vrednost za mpv ``--sub-file-paths`` (relativni pod-folderi uz video).

    Uz uobičajene foldere (``subs``, ``titlovi``…) dodaje i folder po
    epizodi ``subs/<naziv video fajla>``, jer FILMIUM biblioteka drži
    prevode epizode u ``Sezona N/subs/E01 - Naslov/``.
    """

    entries = list(_SUBTITLE_DIR_NAMES)
    entries.append(f"subs/{Path(video_path).stem}")
    return ":".join(entries)


class MpvPlayer:
    """Upravlja jednim ugradjenim mpv procesom."""

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()

    # ----- lokacija exe -----

    @staticmethod
    def executable() -> Path | None:
        candidates = [
            core_paths.root / "bin" / "mpv.exe",
            core_paths.root / "mpv.exe",
            core_paths.root / "bin" / "mpv",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        # Sistemski mpv na PATH-u (apt `mpv` -> /usr/bin/mpv na Linux/Kali; ili
        # mpv.exe na Windows PATH-u) kada nije ugradjen u bin/.
        for _name in ("mpv", "mpv.exe"):
            _found = shutil.which(_name)
            if _found:
                return Path(_found)
        return None

    def available(self) -> bool:
        return self.executable() is not None

    # ----- reprodukcija -----

    def play(
        self,
        video_path: Path,
        window_id: str | None = None,
        geometry: str | None = None,
        subtitle_path: Path | None = None,
    ) -> bool:
        """Pušta video, ugradjen u prozor ``window_id`` na poziciji ``geometry``."""

        exe = self.executable()
        if exe is None:
            return False

        self.stop()  # prekini prethodnu reprodukciju

        args: list[str] = [
            str(exe),
            "--force-window=yes",
            # OSC (mpv-ova kontrola na hover): iskljucena na Windows-u (app crta
            # svoje kontrole nad webview-om); ukljucena na Linux-u/X11 jer je mpv
            # zaseban --ontop native prozor pa HTML kontrole aplikacije ostaju
            # ISPOD njega i ne vide se — mpv OSC je jedina vidljiva kontrola.
            "--osc=no" if _IS_WIN else "--osc=yes",
            # kursor se sakriva posle mirovanja; pokret misa vraca OSC.
            "--cursor-autohide=1500",
            "--no-border",
            # Zaseban prozor IZNAD (WebView2 prekriva native --wid prozor),
            # ali ga GUI „lepi" za region (prati pomeranje/resize prozora).
            "--ontop",
            "--no-window-dragging",
            f"--title={_WINDOW_TITLE}",
            f"--input-ipc-server={_PIPE_NAME}",
            # Prevodi: auto + srpski prioritet + poddirektorijumi
            # (uklj. „subs/<naziv epizode>/" folder po epizodi).
            "--sub-auto=all",
            "--slang=srp,scc,hrv,bos,eng",
            f"--sub-file-paths={build_sub_file_paths(video_path)}",
        ]

        # ``geometry`` su EKRANSKE koordinate regiona (WxH+X+Y).
        if geometry:
            args.append(f"--geometry={geometry}")
        if subtitle_path is not None:
            args.append(f"--sub-file={subtitle_path}")

        _ = window_id  # --wid se namerno ne koristi (skriva se iza webview-a)
        args.append(str(video_path))

        try:
            with self._lock:
                self._process = subprocess.Popen(args)
        except OSError:
            return False

        return True

    # ----- kontrola preko IPC-a -----

    def _send(self, command: list) -> bool:
        """Šalje mpv IPC komandu (Windows imenovani pajp)."""

        payload = (json.dumps({"command": command}) + "\n").encode("utf-8")
        try:
            if _IS_WIN:
                with open(_PIPE_NAME, "r+b", buffering=0) as pipe:
                    pipe.write(payload)
            else:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    sock.connect(_PIPE_NAME)
                    sock.sendall(payload)
                finally:
                    sock.close()
        except OSError:
            return False
        return True

    def pause_toggle(self) -> bool:
        return self._send(["cycle", "pause"])

    def seek(self, seconds: float) -> bool:
        return self._send(["seek", seconds, "relative"])

    def set_fullscreen(self, enabled: bool) -> bool:
        return self._send(["set_property", "fullscreen", bool(enabled)])

    def stop(self) -> bool:
        self._send(["quit"])
        with self._lock:
            process = self._process
            self._process = None
        if process is None:
            return False
        try:
            if process.poll() is None:
                process.terminate()
        except OSError:
            pass
        return True

    def is_running(self) -> bool:
        with self._lock:
            return self._process is not None and self._process.poll() is None

    def _reposition_linux(self, geometry: str) -> bool:
        """Linux/X11: pomeri/resize mpv overlay prozor preko `xdotool` (nalazi ga
        po naslovu `_WINDOW_TITLE`). Vraća False bez xdotool-a ili na Wayland-u."""
        if shutil.which("xdotool") is None:
            return False
        try:
            size, _, rest = geometry.partition("+")
            width_str, _, height_str = size.partition("x")
            x_str, _, y_str = rest.partition("+")
            width, height = int(width_str), int(height_str)
            pos_x, pos_y = int(x_str), int(y_str)
        except (ValueError, AttributeError):
            return False
        if width < 2 or height < 2:
            return False
        try:
            found = subprocess.run(
                ["xdotool", "search", "--name", _WINDOW_TITLE],
                capture_output=True, text=True, timeout=3, check=False,
            )
            wids = [w for w in found.stdout.split() if w.strip()]
            if not wids:
                return False
            wid = wids[-1]
            subprocess.run(["xdotool", "windowsize", wid, str(width), str(height)], timeout=3, check=False)
            subprocess.run(["xdotool", "windowmove", wid, str(pos_x), str(pos_y)], timeout=3, check=False)
            subprocess.run(["xdotool", "windowraise", wid], timeout=3, check=False)
        except (OSError, subprocess.SubprocessError):
            return False
        return True

    def reposition(self, geometry: str) -> bool:
        """Pomeri/resize mpv overlay prozor na ekranske koordinate WxH+X+Y."""

        if not sys.platform.startswith("win"):
            return self._reposition_linux(geometry)

        try:
            size, _, rest = geometry.partition("+")
            width_str, _, height_str = size.partition("x")
            x_str, _, y_str = rest.partition("+")
            width = int(width_str)
            height = int(height_str)
            pos_x = int(x_str)
            pos_y = int(y_str)
        except (ValueError, AttributeError):
            return False

        try:
            import ctypes

            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW(None, _WINDOW_TITLE)
            if not hwnd:
                return False
            # HWND_TOPMOST = -1, SWP_NOACTIVATE = 0x0010
            user32.SetWindowPos(
                hwnd, -1, pos_x, pos_y, width, height, 0x0010
            )
        except OSError:
            return False
        return True


# Deljena instanca za ceo CORE (svi domeni koriste isti plejer).
mpv_player = MpvPlayer()
