// ==========          CORE mpv PLEJER (portable, --wid)          ==========
//
// Ugradjeni mpv plejer: backend pokrece portable mpv.exe i ugradjuje video u
// prozor aplikacije preko HWND (--wid) na tacnoj poziciji (--geometry).
// Kontrola (pauza/seek/stop/fullscreen) ide preko CORE API-ja; HWND se dobija
// iz Tauri-ja.

import { getJson, postJson } from "./httpClient";

const LIBRARY_ENDPOINT = "/api/v1/filmium/libraries";
const PLAYER_ENDPOINT = "/api/v1/player";

type TauriInvoke = (
  command: string,
  args?: Record<string, unknown>,
) => Promise<unknown>;

function getInvoke(): TauriInvoke | null {
  const tauri = (window as unknown as {
    __TAURI__?: { core?: { invoke?: TauriInvoke } };
  }).__TAURI__;
  return tauri?.core?.invoke ?? null;
}

/** Native handle glavnog prozora (za --wid). Radi samo u Tauri desktopu. */
export async function getMainHwnd(): Promise<string | null> {
  const invoke = getInvoke();
  if (!invoke) {
    return null;
  }
  try {
    const hwnd = await invoke("core_main_hwnd");
    return typeof hwnd === "string" && hwnd.length > 0 ? hwnd : null;
  } catch {
    return null;
  }
}

/** Pozicija klijent-oblasti prozora (fizicki px) + scale factor. */
export async function getWindowGeom(): Promise<{
  x: number;
  y: number;
  scale: number;
} | null> {
  const invoke = getInvoke();
  if (!invoke) {
    // Electron/browser: nema Tauri-ja. Pozicija prozora na ekranu preko
    // window.screenX/screenY (× devicePixelRatio za fizičke px). Tako mpv
    // overlay dobija tačne EKRANSKE koordinate i van Tauri desktopa.
    try {
      const scale = window.devicePixelRatio || 1;
      return {
        x: Math.round((window.screenX || 0) * scale),
        y: Math.round((window.screenY || 0) * scale),
        scale,
      };
    } catch {
      return null;
    }
  }
  try {
    const g = (await invoke("core_window_geom")) as [number, number, number];
    return { x: g[0], y: g[1], scale: g[2] || 1 };
  } catch {
    const scale = window.devicePixelRatio || 1;
    return {
      x: Math.round((window.screenX || 0) * scale),
      y: Math.round((window.screenY || 0) * scale),
      scale,
    };
  }
}

/** Da li je mpv.exe dostupan na backendu. */
export async function isMpvAvailable(): Promise<boolean> {
  try {
    const status = await getJson<{ available: boolean; running: boolean }>(
      `${PLAYER_ENDPOINT}/mpv/status`,
    );
    return status.available;
  } catch {
    return false;
  }
}

/** Pusta video u mpv overlay-u na poziciji (geometry) + prevod (source). */
export async function playMpvVideo(
  rootId: number,
  source: string,
  windowId: string | null,
  geometry: string,
  subtitle: string | null = null,
): Promise<boolean> {
  try {
    const result = await postJson<
      { launched: boolean },
      {
        window_id: string | null;
        geometry: string;
        subtitle: string | null;
      }
    >(
      `${LIBRARY_ENDPOINT}/${rootId}/play-mpv`
        + `?source=${encodeURIComponent(source)}`,
      { window_id: windowId, geometry, subtitle },
    );
    return result.launched;
  } catch {
    return false;
  }
}

/** Pomeri/resize mpv overlay na nove ekranske koordinate (WxH+X+Y). */
export async function mpvReposition(geometry: string): Promise<void> {
  try {
    await postJson(`${PLAYER_ENDPOINT}/mpv/reposition`, { geometry });
  } catch {
    /* ignore */
  }
}

export async function mpvPause(): Promise<void> {
  try {
    await postJson(`${PLAYER_ENDPOINT}/mpv/pause`, {});
  } catch {
    /* ignore */
  }
}

export async function mpvSeek(seconds: number): Promise<void> {
  try {
    await postJson(`${PLAYER_ENDPOINT}/mpv/seek`, { seconds });
  } catch {
    /* ignore */
  }
}

export async function mpvFullscreen(enabled: boolean): Promise<void> {
  try {
    await postJson(`${PLAYER_ENDPOINT}/mpv/fullscreen`, { enabled });
  } catch {
    /* ignore */
  }
}

export async function mpvStop(): Promise<void> {
  try {
    await postJson(`${PLAYER_ENDPOINT}/mpv/stop`, {});
  } catch {
    /* ignore */
  }
}
