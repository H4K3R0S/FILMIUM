# NADOGRADNJA (sledeća po rasporedu) — Linux/Kali migracija + native zavisnosti

> Mesto u planu razvoja: **sledeća stavka po rasporedu.** Cilj: FILMIUM ćelija
> radi na Kali/Debian Linux-u isto kao na Windows-u. Ovde je popis šta je
> Windows-zavisno, šta se menja za Linux, a šta ne treba dirati.

## 1. Native binarne iz CORE `bin/` koje pripadaju FILMIUM-u

### mpv (plejer) — **pripada FILMIUM-u**
- **Windows sada:** `CORE/bin/mpv.exe` (portable, ~64 MB), proba `core/foundation/dependencies.py`
  → `_mpv_installed()` gleda `bin/mpv.exe`; plejer sa overlay-om.
- **Uputstvo (Windows, kako je sada):** portable `mpv.exe` stoji u `bin/`; INSTALL dugme
  (dependency panel) preuzima portable zip u `bin/`. Ništa se ne instalira sistemski.
- **Linux/Kali:** ne koristi se `.exe`. Instaliraj sistemski:
  ```bash
  sudo apt update && sudo apt install -y mpv libmpv2
  ```
  - Proba treba da postane: `shutil.which("mpv")` (PATH) **ILI** `bin/mpv` — vidi §3.
  - Ako se koristi `libmpv` (embed render), paket je `libmpv2` (Debian/Kali) / `libmpv-dev` za build.
- **Zaključak:** na Linux-u mpv je native paket, portable `.exe` logika se gasi.

## 2. Ostale FILMIUM zavisnosti — Windows vs Linux

| Alat | Uloga | Windows sada | Linux/Kali |
|------|-------|--------------|------------|
| **ffmpeg/ffprobe** | rezolucija/kodek/FPS pri uvozu | `winget install Gyan.FFmpeg` | `sudo apt install ffmpeg` (ffprobe u paketu) |
| **VLC** | alternativni plejer | putanja `.exe` | `sudo apt install vlc`; probu vezati za `which vlc` |
| **qbittorrent-api** | torrent (Python paket) | `pip install qbittorrent-api` | isto (cross-platform) — **ne menja se** |
| **deep-translator** | prevod opisa/titlova | `pip install deep-translator` | isto — **ne menja se** |
| **Pillow** | posteri/thumbnail | `pip install Pillow` | isto — **ne menja se** |
| **Node.js** | build GUI (Vite/Tauri) | nodejs.org | `sudo apt install nodejs npm` ili nvm |
| **git** | (opšte) | `winget install Git.Git` | `sudo apt install git` |

## 3. Kod koji treba dirati (Windows-specifično)

- `core/foundation/dependencies.py`:
  - `_mpv_installed()` — dodati Linux granu (`shutil.which("mpv")` uz `bin/mpv`).
  - `install_hint` / `installer` — na Linux-u `winget` ne postoji; hint → `apt` komanda.
    Uslovno po `sys.platform` (`win32` vs `linux`).
- `core/foundation/installer.py` — WINGET/PORTABLE_ZIP staze su Windows; na Linux-u
  `apt`/`pip` (ili samo prikaži hint, bez auto-instalacije koja traži `sudo`).
- Bilo koja tvrda `.exe` putanja ili `\\` separator → `pathlib` + bez ekstenzije.
- Tauri prozor: isto radi na Linux-u (webkit2gtk), ali treba `libwebkit2gtk-4.1-dev`,
  `libgtk-3-dev`, `librsvg2-dev`, `build-essential` za build.

## 4. Šta NE treba dirati (radi isto na oba)

- Python API sloj (FastAPI/uvicorn), SQLite baza, RAG (Postgres opciono).
- GUI (React/Vite) — čist web, platform-agnostičan.
- Domenska logika (biblioteka, torrenti, kolekcije, kurator) — čist Python.
- Pydantic šeme, rute, `deep-translator`, `qbittorrent-api`, `Pillow`.

## 5. Redosled primene
1. Apstrahuj `dependencies.py` po platformi (`sys.platform`) — mpv/ffmpeg/vlc probe + hint.
2. Instaliraj Kali sistemske pakete (`mpv libmpv2 ffmpeg vlc nodejs npm git`).
3. Build alati za Tauri (`libwebkit2gtk-4.1-dev` …), pa `cargo tauri build`.
4. Test: uvoz videa (ffprobe), plejer (mpv/libmpv), torrent, prevod.
