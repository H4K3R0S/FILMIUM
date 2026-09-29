import {
  useEffect,
  useRef,
  useState,
} from "react";
import {
  Globe,
  Languages,
  Maximize,
  MonitorPlay,
  Pause,
  Play,
  RotateCcw,
  RotateCw,
  Square,
  Zap,
} from "lucide-react";

import {
  getMainHwnd,
  getWindowGeom,
  isMpvAvailable,
  mpvFullscreen,
  mpvPause,
  mpvReposition,
  mpvSeek,
  mpvStop,
} from "../../../../services/filmiumPlayer";
import FilmiumTranslationSidebar from "./FilmiumTranslationSidebar";


// ==========          TIPOVI          ==========

export type FilmiumSubtitleTrack = {
  src: string;
  lang: string;
  label: string;
  isDefault?: boolean;
};

// „web" = direktan izvor (brzo, seek za H.264); „compat" = univerzalni tok
// (ffmpeg remux/transcode) unutar NAŠEG plejera — svi kodeci, bez spoljne app.
type PlayerEngine = "web" | "compat" | "mpv";

const ENGINE_KEY = "filmium:player-engine";

type FilmiumPlayerProps = {
  src: string | null;
  fallbackSrc?: string | null;
  poster?: string | null;
  subtitles?: FilmiumSubtitleTrack[];
  autoPlay?: boolean;
  emptyLabel?: string;
  /** mpv režim: pušta trenutni sadržaj ugradjen u prozor (--wid). */
  onNativePlay?: (opts: {
    windowId: string | null;
    geometry: string;
  }) => Promise<boolean>;
  /** Javljanje trenutnog vremena (ms) — npr. za „Edit Prevoda". */
  onTimeUpdateMs?: (ms: number) => void;
};


// ==========          FILMIUM INLINE PLEJER          ==========

/**
 * Ugrađeni HTML5 plejer (radi u Tauri webview-u).
 *
 * Prečice dok je stranica aktivna: Space = pusti/pauza; strelice
 * levo/desno = ±5s (držanje ubrzava kroz auto-repeat); Enter = ceo
 * ekran (Enter/Esc izlaz). Prevodi se učitavaju kao <track> (sr prvi).
 */
function FilmiumPlayer({
  src,
  fallbackSrc,
  poster,
  subtitles = [],
  autoPlay = false,
  emptyLabel = "Video nije dostupan.",
  onNativePlay,
  onTimeUpdateMs,
}: FilmiumPlayerProps) {
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const mpvRegionRef = useRef<HTMLDivElement | null>(null);

  // Režim: „web" (direktno), „compat" (ffmpeg tok) ili „mpv" (ugradjen mpv).
  const [engine, setEngine] = useState<PlayerEngine>(() => {
    try {
      const saved = window.localStorage.getItem(ENGINE_KEY);
      return saved === "compat" || saved === "mpv" ? saved : "web";
    } catch {
      return "web";
    }
  });

  const [mpvAvailable, setMpvAvailable] = useState(false);
  const [mpvPaused, setMpvPaused] = useState(false);
  // Pamti se za KOJI izvor je mpv pokrenut: promena izvora time sama znači da
  // više nije pokrenut, pa efekat nema šta sinhrono da upiše.
  const [pokrenutZa, setPokrenutZa] = useState<string | null>(null);
  const mpvStarted = engine === "mpv" && pokrenutZa !== null && pokrenutZa === src;

  useEffect(() => {
    let active = true;
    void isMpvAvailable().then((ok) => {
      if (active) {
        setMpvAvailable(ok);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  /**
   * Ekranska geometrija (WxH+X+Y) mpv regiona = pozicija prozora + offset
   * regiona (× scale factor za HiDPI).
   */
  async function computeMpvGeometry(): Promise<string | null> {
    const rect = mpvRegionRef.current?.getBoundingClientRect();
    if (!rect || rect.width < 2 || rect.height < 2) {
      return null;
    }
    const geom = await getWindowGeom();
    const scale = geom?.scale ?? window.devicePixelRatio ?? 1;
    const baseX = geom?.x ?? 0;
    const baseY = geom?.y ?? 0;
    const x = Math.round(baseX + rect.left * scale);
    const y = Math.round(baseY + rect.top * scale);
    const w = Math.round(rect.width * scale);
    const h = Math.round(rect.height * scale);
    return `${w}x${h}+${x}+${y}`;
  }

  /**
   * Pokreće mpv u regionu (tek na klik — ne automatski).
   */
  async function startMpv(): Promise<void> {
    if (!src || !onNativePlay) {
      return;
    }
    const windowId = await getMainHwnd();
    const geometry = (await computeMpvGeometry()) ?? "0x0+0+0";
    const ok = await onNativePlay({ windowId, geometry });
    if (ok) {
      setPokrenutZa(src);
      setMpvPaused(false);
    }
  }

  // Zaustavi mpv kad se promeni izvor, izadje iz mpv režima ili odmontira.
  useEffect(() => {
    if (engine !== "mpv") {
      // Izlazak iz mpv režima: sam prikaz već zna da mpv ne radi (`mpvStarted`
      // traži `engine === "mpv"`), pa ostaje samo da se proces zaustavi.
      void mpvStop();
      return;
    }
    return () => {
      void mpvStop();
      setPokrenutZa(null);
    };
  }, [engine, src]);

  // Lepljenje: prati pomeranje/resize prozora i regiona → repozicioniraj mpv.
  useEffect(() => {
    if (engine !== "mpv" || !mpvStarted) {
      return;
    }

    let raf = 0;
    const sync = (): void => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        void computeMpvGeometry().then((g) => {
          if (g) {
            void mpvReposition(g);
          }
        });
      });
    };

    window.addEventListener("resize", sync);
    window.addEventListener("scroll", sync, true);
    // Electron/X11 ne emituje event na pomeranje prozora — poll-uj poziciju.
    const moveTimer = window.setInterval(sync, 500);

    const observer = new ResizeObserver(sync);
    if (mpvRegionRef.current) {
      observer.observe(mpvRegionRef.current);
    }

    // Tauri pomeranje/resize prozora.
    const tauriWindow = (window as unknown as {
      __TAURI__?: {
        window?: { getCurrentWindow?: () => {
          onMoved?: (cb: () => void) => Promise<() => void>;
          onResized?: (cb: () => void) => Promise<() => void>;
        } };
      };
    }).__TAURI__?.window?.getCurrentWindow?.();

    const unlisteners: Array<() => void> = [];
    if (tauriWindow) {
      void tauriWindow.onMoved?.(sync).then((u) => unlisteners.push(u));
      void tauriWindow.onResized?.(sync).then((u) => unlisteners.push(u));
    }

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", sync);
      window.removeEventListener("scroll", sync, true);
      window.clearInterval(moveTimer);
      observer.disconnect();
      unlisteners.forEach((u) => u());
    };
  }, [engine, mpvStarted]);

  function chooseEngine(next: PlayerEngine): void {
    setEngine(next);
    try {
      window.localStorage.setItem(ENGINE_KEY, next);
    } catch {
      /* ignore */
    }
  }

  // U „compat" režimu odmah koristimo univerzalni tok (fallbackSrc).
  const effectiveSrc =
    engine === "compat" ? (fallbackSrc ?? src) : src;

  // Prebacivanje na univerzalni tok (posle greške kodeka) pamti se UZ izvor
  // zbog koga je nastalo. Kad se izvor ili režim promene, prikaz se vraća na
  // ono što traži režim — bez upisa iz efekta, koji je značio jedan kadar sa
  // prethodnim izvorom u `<video>` elementu.
  const [prebaceno, setPrebaceno] = useState<{
    osnova: string | null;
    src: string | null;
  } | null>(null);

  const prebacivanjeVazi = prebaceno?.osnova === effectiveSrc;
  const activeSrc = prebacivanjeVazi ? prebaceno.src : effectiveSrc;
  const isTranscoding = prebacivanjeVazi || engine === "compat";

  // ----- Prevodni Sidebar -----

  const [showTranslation, setShowTranslation] = useState(false);
  const [currentTimeMs, setCurrentTimeMs] = useState(0);
  const subtitleSrc =
    subtitles.find((track) => track.isDefault)?.src
    ?? subtitles[0]?.src
    ?? null;

  function openTranslation(): void {
    // Otvaranje panela pauzira reprodukciju (pregled prevoda u miru).
    if (engine === "mpv") {
      void mpvPause();
      setMpvPaused(true);
    } else {
      const video = videoRef.current;
      video?.pause();
      // Pauziran video ne šalje timeupdate — uhvati trenutak odmah da panel
      // pokaže prevod iz vremena pauze, a ne nulu/zastareo cue.
      if (video) {
        setCurrentTimeMs(video.currentTime * 1000);
      }
    }
    setShowTranslation(true);
  }

  const translationButton = subtitles.length > 0 && (
    <button
      className={`filmium-player-translate${showTranslation ? " active" : ""}`}
      onClick={() =>
        showTranslation ? setShowTranslation(false) : openTranslation()}
      title="Prevod — pauzira i otvara panel"
      type="button"
    >
      <Languages size={14} /> Prevod
    </button>
  );

  const translationSidebar = (
    <FilmiumTranslationSidebar
      currentTimeMs={currentTimeMs}
      onClose={() => setShowTranslation(false)}
      onSeek={
        engine === "mpv"
          ? undefined
          : (ms) => {
              if (videoRef.current) {
                videoRef.current.currentTime = ms / 1000;
              }
            }
      }
      open={showTranslation}
      subtitleSrc={subtitleSrc}
    />
  );

  // ----- Prečice sa tastature -----

  useEffect(() => {
    function isInteractive(target: EventTarget | null): boolean {
      const element = target as HTMLElement | null;
      if (!element) {
        return false;
      }
      const tag = element.tagName;
      return (
        tag === "INPUT"
        || tag === "TEXTAREA"
        || tag === "SELECT"
        || tag === "BUTTON"
        || tag === "A"
        || element.isContentEditable
      );
    }

    function toggleFullscreen(): void {
      if (document.fullscreenElement) {
        void document.exitFullscreen();
      } else {
        void wrapperRef.current?.requestFullscreen();
      }
    }

    function handleKey(event: KeyboardEvent): void {
      if (isInteractive(event.target)) {
        return;
      }

      // mpv režim: prečice idu na ugradjeni mpv (preko CORE API-ja).
      if (engine === "mpv") {
        switch (event.key) {
          case " ":
          case "Spacebar":
            event.preventDefault();
            void mpvPause();
            setMpvPaused((paused) => !paused);
            break;
          case "ArrowRight":
            event.preventDefault();
            void mpvSeek(5);
            break;
          case "ArrowLeft":
            event.preventDefault();
            void mpvSeek(-5);
            break;
          default:
            break;
        }
        return;
      }

      const video = videoRef.current;
      if (!video || !src) {
        return;
      }

      // Kada je sam video fokusiran, native kontrole već obrađuju Space i
      // strelice — preskačemo da se akcija ne izvrši dvaput.
      const videoFocused = document.activeElement === video;

      switch (event.key) {
        case " ":
        case "Spacebar":
          if (videoFocused) {
            return;
          }
          event.preventDefault();
          if (video.paused) {
            void video.play();
          } else {
            video.pause();
          }
          break;

        case "ArrowRight":
          if (videoFocused) {
            return;
          }
          event.preventDefault();
          video.currentTime = Math.min(
            video.duration || video.currentTime + 5,
            video.currentTime + 5,
          );
          break;

        case "ArrowLeft":
          if (videoFocused) {
            return;
          }
          event.preventDefault();
          video.currentTime = Math.max(0, video.currentTime - 5);
          break;

        case "Enter":
          event.preventDefault();
          toggleFullscreen();
          break;

        case "Escape":
          if (document.fullscreenElement) {
            void document.exitFullscreen();
          }
          break;

        default:
          break;
      }
    }

    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [src, engine]);

  // ----- Ponovno učitavanje pri promeni izvora -----

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !activeSrc) {
      return;
    }
    video.load();
    if (autoPlay) {
      void video.play().catch(() => {
        /* autoplay može biti blokiran — tada korisnik pusti ručno */
      });
    }
  }, [activeSrc, autoPlay]);

  /**
   * Prelazi na prekodiranje SAMO za prave greške kodeka (dekodiranje /
   * nepodržan izvor). Mrežne i prekinute greške ne pokreću prekodiranje,
   * da H.264 filmovi ne bi bespotrebno išli kroz ffmpeg.
   */
  /**
   * Na grešku kodeka/kontejnera prelazi na kompatibilan tok (ffmpeg remux/
   * transcode) — sve ostaje unutar ugrađenog plejera.
   */
  function handleError(): void {
    const code = videoRef.current?.error?.code;
    const isCodecError =
      code === 3 /* MEDIA_ERR_DECODE */
      || code === 4; /* MEDIA_ERR_SRC_NOT_SUPPORTED */

    if (
      isCodecError
      && fallbackSrc
      && activeSrc !== fallbackSrc
    ) {
      setPrebaceno({ osnova: effectiveSrc, src: fallbackSrc });
    }
  }

  // Prekidač režima (Web / Univerzalno) — vidi se uvek. Oba renderuju u
  // NAŠEM plejeru; „Univerzalno" ide kroz ffmpeg tok (svi kodeci).
  const engineToggle = (
    <div className="filmium-player-engine" role="group">
      <button
        className={engine === "web" ? "active" : ""}
        onClick={() => chooseEngine("web")}
        title="Direktan izvor (brzo, seek za H.264)"
        type="button"
      >
        <Globe size={13} /> Web
      </button>
      <button
        className={engine === "compat" ? "active" : ""}
        onClick={() => chooseEngine("compat")}
        title="Univerzalni tok (ffmpeg) — svi kodeci, u aplikaciji"
        type="button"
      >
        <Zap size={13} /> Univerzalno
      </button>
      <button
        className={engine === "mpv" ? "active" : ""}
        onClick={() => chooseEngine("mpv")}
        title="Ugradjeni mpv (svi kodeci, u aplikaciji)"
        type="button"
      >
        <MonitorPlay size={13} /> mpv
      </button>
    </div>
  );

  // ----- mpv (ugradjen preko --wid) režim -----
  if (engine === "mpv") {
    return (
      <div className="filmium-player-inline" ref={wrapperRef}>
        {engineToggle}
        {translationButton}
        {translationSidebar}

        {/* mpv crta preko ovog regiona (native prozor iznad webview-a) */}
        <div
          className="filmium-player-mpv-region"
          ref={mpvRegionRef}
          style={
            poster && !mpvStarted
              ? { backgroundImage: `url("${poster}")` }
              : undefined
          }
        >
          {!mpvAvailable ? (
            <span className="filmium-player-vlc-warn">
              mpv nije pronađen — instaliraj sistemski mpv (Linux: „sudo apt install -y mpv").
            </span>
          ) : !mpvStarted ? (
            <button
              className="filmium-player-mpv-start"
              disabled={!src}
              onClick={() => void startMpv()}
              title="Pusti u mpv-u"
              type="button"
            >
              <Play fill="currentColor" size={30} />
            </button>
          ) : null}
        </div>

        <div className="filmium-player-mpv-bar">
          <button
            onClick={() => void mpvSeek(-5)}
            title="Nazad 5s"
            type="button"
          >
            <RotateCcw size={18} />
          </button>
          <button
            className="filmium-player-primary"
            onClick={() => {
              void mpvPause();
              setMpvPaused((paused) => !paused);
            }}
            title="Pusti / pauza"
            type="button"
          >
            {mpvPaused ? (
              <Play fill="currentColor" size={20} />
            ) : (
              <Pause fill="currentColor" size={20} />
            )}
          </button>
          <button
            onClick={() => void mpvSeek(5)}
            title="Napred 5s"
            type="button"
          >
            <RotateCw size={18} />
          </button>
          <button
            onClick={() => void mpvFullscreen(true)}
            title="Ceo ekran"
            type="button"
          >
            <Maximize size={18} />
          </button>
          <button
            onClick={() => void mpvStop()}
            title="Zaustavi"
            type="button"
          >
            <Square size={18} />
          </button>
        </div>
      </div>
    );
  }

  if (!effectiveSrc) {
    return (
      <div className="filmium-player-inline empty">
        {engineToggle}
        <span>{emptyLabel}</span>
      </div>
    );
  }

  return (
    <div className="filmium-player-inline" ref={wrapperRef}>
      {engineToggle}
      {translationButton}
      {translationSidebar}

      <video
        className="filmium-player-inline-video"
        controls
        crossOrigin={subtitles.length > 0 ? "anonymous" : undefined}
        key={activeSrc ?? ""}
        onError={handleError}
        onPause={(event) => {
          const ms = event.currentTarget.currentTime * 1000;
          setCurrentTimeMs(ms);
          onTimeUpdateMs?.(ms);
        }}
        onTimeUpdate={(event) => {
          const ms = event.currentTarget.currentTime * 1000;
          setCurrentTimeMs(ms);
          onTimeUpdateMs?.(ms);
        }}
        poster={poster ?? undefined}
        ref={videoRef}
      >
        <source src={activeSrc ?? undefined} />

        {subtitles.map((track) => (
          <track
            default={track.isDefault}
            key={track.src}
            kind="subtitles"
            label={track.label}
            src={track.src}
            srcLang={track.lang}
          />
        ))}
      </video>

      {isTranscoding && (
        <span className="filmium-player-transcode-badge">
          Univerzalni tok (svi kodeci)
        </span>
      )}
    </div>
  );
}

export default FilmiumPlayer;
