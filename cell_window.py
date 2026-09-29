#!/usr/bin/env python3
"""Native prozor ćelije (WebKit2GTK) — Tauri-ekvivalent na Linuxu.

Seamless prozor BEZ sistemskog okvira i naslovne trake (min/max/X). Domen
prikazuje SVOJE kontrole (TitleBar) i one se preko JS↔GTK mosta vezuju na
pravi prozor: minimize / toggle-maximize / close + pomeranje (drag) i
promena veličine po ivicama. Server se diže iz venv-a ćelije; zatvaranje
prozora gasi i server.

Pokreće se SISTEMSKIM python3 (za PyGObject/WebKit2).
"""

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)

# NVIDIA + WebKitGTK: podrazumevani DMA-BUF render na NVIDIA proprietarnom
# drajveru često ne dobije GPU kompoziciju i padne na SPOR softverski render
# (trzav skrol). Isključivanje DMA-BUF renderera vraća GPU put na NVIDIA.
# Postavlja se PRE nego što se GTK/WebKit inicijalizuje (pre importa gi).
if os.path.exists("/proc/driver/nvidia/version"):
    os.environ.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")

try:
    CFG = json.loads((ROOT / "cell.json").read_text(encoding="utf-8"))
except Exception:  # noqa: BLE001
    CFG = {}
HOST = "127.0.0.1"
PORT = int(CFG.get("port", 8000))
NAME = CFG.get("name", "Ćelija")
DOMAIN_ID = CFG.get("domain_id", "")
URL = f"http://{HOST}:{PORT}"

# Zona (px) uz ivicu prozora u kojoj mousedown počinje resize.
EDGE = 6


def find_venv_python() -> str:
    for candidate in (".venv/bin/python", ".venv-linux/bin/python"):
        p = ROOT / candidate
        if p.exists():
            return str(p)
    return sys.executable


def port_open() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((HOST, PORT)) == 0


def start_server():
    if port_open():
        return None
    proc = subprocess.Popen(
        [find_venv_python(), "-m", "uvicorn", "cell_app:app", "--host", HOST, "--port", str(PORT)],
        cwd=str(ROOT),
        start_new_session=True,
    )
    for _ in range(80):
        if port_open() or proc.poll() is not None:
            break
        time.sleep(0.25)
    return proc


# JS most: hvata klik na kontrolama i mousedown na drag/resize zonama,
# pa šalje poruku GTK-u. Radi bez Tauri runtime-a (preuzima onClick handlere).
BRIDGE_JS = r"""
(function () {
  var EDGE = %d;
  function send(msg) {
    try { window.webkit.messageHandlers.cellwin.postMessage(msg); } catch (e) {}
  }

  // --- Kontrole (min/max/close): preuzmi klik pre React/Tauri handlera ---
  function wireControls() {
    var map = [
      [".titlebar-minimize", "minimize"],
      [".titlebar-maximize", "toggle-maximize"],
      [".titlebar-close", "close"],
    ];
    map.forEach(function (pair) {
      document.querySelectorAll(pair[0]).forEach(function (btn) {
        if (btn.__cellwin) return;
        btn.__cellwin = true;
        btn.addEventListener("click", function (e) {
          e.preventDefault();
          e.stopImmediatePropagation();
          send(pair[1]);
        }, true);
      });
    });
  }

  // --- Pomeranje prozora preko drag-region trake ---
  document.addEventListener("mousedown", function (e) {
    if (e.button !== 0) return;
    // Resize po ivicama celog prozora
    var x = e.clientX, y = e.clientY;
    var w = window.innerWidth, h = window.innerHeight;
    var L = x <= EDGE, R = x >= w - EDGE, T = y <= EDGE, B = y >= h - EDGE;
    if (L || R || T || B) {
      var dir = (T ? "top" : B ? "bottom" : "") + (L ? "-left" : R ? "-right" : "");
      dir = dir.replace(/^-/, "");
      if (dir) { e.preventDefault(); send("resize:" + dir); return; }
    }
    // Drag traka (ali ne na dugmadima/kontrolama)
    var region = e.target.closest("[data-tauri-drag-region]");
    if (region && !e.target.closest("button, a, input, .titlebar-button")) {
      e.preventDefault();
      send("start-drag");
    }
  }, true);

  // Dupli klik na traku => toggle maximize
  document.addEventListener("dblclick", function (e) {
    var region = e.target.closest("[data-tauri-drag-region]");
    if (region && !e.target.closest("button, a, input, .titlebar-button")) {
      send("toggle-maximize");
    }
  }, true);

  if (document.readyState !== "loading") wireControls();
  else document.addEventListener("DOMContentLoaded", wireControls);
  // React montira kasnije — ponovi vezivanje nekoliko puta.
  var n = 0, iv = setInterval(function () { wireControls(); if (++n > 25) clearInterval(iv); }, 250);
})();
""" % EDGE  # noqa: UP031


def main() -> int:
    server = start_server()

    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, GdkPixbuf, Gtk, WebKit2

    win = Gtk.Window(title=NAME)
    win.set_default_size(1280, 800)
    win.set_position(Gtk.WindowPosition.CENTER)
    win.set_decorated(False)  # BEZ sistemskog okvira i naslovne trake
    win.set_wmclass(NAME, NAME)

    icon_path = ROOT / f"{DOMAIN_ID}-icon.png"
    if icon_path.is_file():
        try:
            win.set_icon(GdkPixbuf.Pixbuf.new_from_file(str(icon_path)))
        except Exception:  # noqa: BLE001, S110
            pass

    ucm = WebKit2.UserContentManager()
    ucm.register_script_message_handler("cellwin")
    webview = WebKit2.WebView.new_with_user_content_manager(ucm)

    # Performanse renderovanja/skrola: uključi GPU kompoziciju i glatki skrol.
    try:
        settings = webview.get_settings()
        settings.set_hardware_acceleration_policy(
            WebKit2.HardwareAccelerationPolicy.ALWAYS
        )
        settings.set_enable_smooth_scrolling(True)
    except Exception:  # noqa: BLE001, S110
        pass

    # Svež GUI pri svakom otvaranju (bundle se menja pri rebuild-u); localStorage ostaje.
    try:
        webview.get_context().clear_cache()
    except Exception:  # noqa: BLE001, S110
        pass

    script = WebKit2.UserScript.new(
        BRIDGE_JS,
        WebKit2.UserContentInjectedFrames.TOP_FRAME,
        WebKit2.UserScriptInjectionTime.START,
        None,
        None,
    )
    ucm.add_script(script)

    EDGE_MAP = {
        "top": Gdk.WindowEdge.NORTH,
        "bottom": Gdk.WindowEdge.SOUTH,
        "left": Gdk.WindowEdge.WEST,
        "right": Gdk.WindowEdge.EAST,
        "top-left": Gdk.WindowEdge.NORTH_WEST,
        "top-right": Gdk.WindowEdge.NORTH_EAST,
        "bottom-left": Gdk.WindowEdge.SOUTH_WEST,
        "bottom-right": Gdk.WindowEdge.SOUTH_EAST,
    }

    def pointer_xy():
        try:
            seat = win.get_display().get_default_seat()
            _screen, x, y = seat.get_pointer().get_position()
            return x, y
        except Exception:  # noqa: BLE001
            return 0, 0

    def on_message(_ucm, result):
        # WebKit2 4.1: result može biti JSCValue ili JavascriptResult.
        try:
            action = result.to_string()
        except Exception:  # noqa: BLE001
            try:
                action = result.get_js_value().to_string()
            except Exception:  # noqa: BLE001
                return

        if action == "minimize":
            win.iconify()
        elif action == "toggle-maximize":
            (win.unmaximize if win.is_maximized() else win.maximize)()
        elif action == "close":
            win.close()
        elif action == "start-drag":
            x, y = pointer_xy()
            win.begin_move_drag(1, int(x), int(y), Gdk.CURRENT_TIME)
        elif action.startswith("resize:"):
            edge = EDGE_MAP.get(action.split(":", 1)[1])
            if edge is not None:
                x, y = pointer_xy()
                win.begin_resize_drag(edge, 1, int(x), int(y), Gdk.CURRENT_TIME)

    ucm.connect("script-message-received::cellwin", on_message)

    load_url = f"{URL}/?_cb={int(time.time())}"
    webview.load_uri(load_url)
    win.add(webview)

    def on_destroy(*_a):
        if server is not None:
            try:
                os.killpg(os.getpgid(server.pid), signal.SIGTERM)
            except Exception:  # noqa: BLE001
                try:
                    server.terminate()
                except Exception:  # noqa: BLE001, S110
                    pass
        Gtk.main_quit()

    win.connect("destroy", on_destroy)
    win.maximize()  # hint pre mapiranja: pouzdanije maksimizovanje undecorated prozora
    win.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
