import { useEffect, useRef } from "react";
import { useLocation } from "react-router";

import { useBootReveal } from "../boot/useBootReveal";
import { resolveDomainId } from "../../lib/domainTheme";
import { isAmbientActive, useAmbientSettings } from "./ambientEffect";
import "./ambient.css";


// ==========          AMBIENT POZADINA (CONNECTED DOTS)          ==========
/*
 * Slojevi (od dole): crna podloga → maglovити glow spotovi (blur) → povezane
 * tačke. Sve je čisto dekorativno i ne hvata pokazivač (pointer-events: none).
 * Boje uzima iz --ambient-dot-rgb / --ambient-dot-2-rgb tokena aktivne teme,
 * pa prati identitet domena. Pojavljuje se ~5s po paljenju i raste ~5s.
 */

/** Ukupan broj tačaka. */
const DOT_COUNT = 90;

/** Najveća udaljenost na kojoj se dve tačke povezuju linijom (px). */
const LINK_DISTANCE = 130;

/** Koliko glow spotova lebdi istovremeno (1–3). */
const SPOT_MIN = 1;
const SPOT_MAX = 3;

type Rgb = [number, number, number];

type Dot = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  /** 0 → primarna boja, 1 → sekundarna. */
  tone: number;
};

type Spot = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  /** Trenutna faza životnog ciklusa. */
  phase: "in" | "hold" | "out";
  /** Napredak faze 0..1. */
  t: number;
  /** Broj preostalih pulseva u hold fazi. */
  pulses: number;
  /** Faza pulsiranja (radijani). */
  pulse: number;
};


// ==========          POMOĆNE FUNKCIJE          ==========

/** Slučajan broj u [min, max). */
function rand(min: number, max: number): number {
  return min + Math.random() * (max - min);
}

/** Čita "r, g, b" token boje sa fallback-om. */
function readRgb(styles: CSSStyleDeclaration, name: string, fallback: Rgb): Rgb {
  const raw = styles.getPropertyValue(name).trim();
  const parts = raw.split(",").map((piece) => Number.parseInt(piece, 10));

  if (parts.length === 3 && parts.every((value) => Number.isFinite(value))) {
    return [parts[0], parts[1], parts[2]];
  }

  return fallback;
}


// ==========          KOMPONENTA          ==========

function AmbientBackground() {
  const { pathname } = useLocation();
  const domainId = resolveDomainId(pathname, null);
  const { settings } = useAmbientSettings();

  const active = isAmbientActive(domainId, settings);

  // Efekat počinje da se pojavljuje 5s po paljenju sistema.
  const revealed = useBootReveal(5000);

  const spotCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const dotCanvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (!active) {
      return;
    }

    const spotCanvas = spotCanvasRef.current;
    const dotCanvas = dotCanvasRef.current;

    if (!spotCanvas || !dotCanvas) {
      return;
    }

    const spotCtx = spotCanvas.getContext("2d");
    const dotCtx = dotCanvas.getContext("2d");

    // jsdom / okruženja bez canvas podrške: tiho odustani.
    if (!spotCtx || !dotCtx) {
      return;
    }

    let width = 0;
    let height = 0;

    function resize(): void {
      width = window.innerWidth;
      height = window.innerHeight;

      for (const canvas of [spotCanvas, dotCanvas]) {
        if (canvas) {
          canvas.width = width;
          canvas.height = height;
        }
      }
    }

    resize();
    window.addEventListener("resize", resize);

    // Boje tačaka i spotova iz tokena aktivne teme (osvežava se povremeno
    // da uhvati promenu domena bez ponovnog montiranja).
    let primary: Rgb = [130, 170, 255];
    let secondary: Rgb = [170, 140, 255];

    function refreshColors(): void {
      const styles = window.getComputedStyle(document.documentElement);
      primary = readRgb(styles, "--ambient-dot-rgb", primary);
      secondary = readRgb(styles, "--ambient-dot-2-rgb", secondary);
    }

    refreshColors();

    const dots: Dot[] = Array.from({ length: DOT_COUNT }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: rand(-0.45, 0.45),
      vy: rand(-0.45, 0.45),
      radius: rand(1.2, 3),
      tone: Math.random(),
    }));

    function spawnSpot(): Spot {
      return {
        x: rand(0.1, 0.9) * width,
        y: rand(0.1, 0.9) * height,
        vx: rand(-0.07, 0.07),
        vy: rand(-0.07, 0.07),
        radius: rand(160, 360),
        phase: "in",
        t: 0,
        pulses: Math.round(rand(2, 4)),
        pulse: 0,
      };
    }

    const spotCount = Math.round(rand(SPOT_MIN, SPOT_MAX + 1));
    const spots: Spot[] = Array.from({ length: spotCount }, spawnSpot);

    let frame = 0;
    let raf = 0;

    function drawSpots(): void {
      if (!spotCtx) {
        return;
      }

      spotCtx.clearRect(0, 0, width, height);

      for (let i = 0; i < spots.length; i += 1) {
        const spot = spots[i];

        spot.x += spot.vx;
        spot.y += spot.vy;

        // Životni ciklus: fade-in → pulsiranje (hold) → fade-out → respawn.
        // Bez početne vrednosti: sve tri grane je postavljaju, pa bi nula bila
        // laž koju niko ne čita.
        let visibility: number;

        if (spot.phase === "in") {
          spot.t += 0.005;
          visibility = spot.t;

          if (spot.t >= 1) {
            spot.phase = "hold";
            spot.t = 0;
          }
        } else if (spot.phase === "hold") {
          spot.pulse += 0.02;
          visibility = 0.7 + 0.3 * Math.sin(spot.pulse);

          if (spot.pulse >= Math.PI * 2 * spot.pulses) {
            spot.phase = "out";
            spot.t = 0;
          }
        } else {
          spot.t += 0.005;
          visibility = 1 - spot.t;

          if (spot.t >= 1) {
            spots[i] = spawnSpot();
            continue;
          }
        }

        const alpha = Math.max(0, Math.min(1, visibility)) * 0.3;
        const [r, g, b] = i % 2 === 0 ? primary : secondary;

        const gradient = spotCtx.createRadialGradient(
          spot.x,
          spot.y,
          0,
          spot.x,
          spot.y,
          spot.radius,
        );
        gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${alpha})`);
        gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);

        spotCtx.fillStyle = gradient;
        spotCtx.beginPath();
        spotCtx.arc(spot.x, spot.y, spot.radius, 0, Math.PI * 2);
        spotCtx.fill();
      }
    }

    function drawDots(): void {
      if (!dotCtx) {
        return;
      }

      dotCtx.clearRect(0, 0, width, height);

      for (const dot of dots) {
        dot.x += dot.vx;
        dot.y += dot.vy;

        if (dot.x < 0 || dot.x > width) {
          dot.vx *= -1;
        }
        if (dot.y < 0 || dot.y > height) {
          dot.vy *= -1;
        }

        const [r, g, b] =
          dot.tone < 0.5 ? primary : secondary;

        dotCtx.beginPath();
        dotCtx.arc(dot.x, dot.y, dot.radius, 0, Math.PI * 2);
        dotCtx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.75)`;
        dotCtx.fill();
      }

      // Linije između bliskih tačaka; providnost opada sa udaljenošću.
      const [lr, lg, lb] = primary;

      for (let i = 0; i < dots.length; i += 1) {
        for (let j = i + 1; j < dots.length; j += 1) {
          const dx = dots[i].x - dots[j].x;
          const dy = dots[i].y - dots[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < LINK_DISTANCE) {
            const alpha = (1 - dist / LINK_DISTANCE) * 0.28;
            dotCtx.beginPath();
            dotCtx.moveTo(dots[i].x, dots[i].y);
            dotCtx.lineTo(dots[j].x, dots[j].y);
            dotCtx.strokeStyle = `rgba(${lr}, ${lg}, ${lb}, ${alpha})`;
            dotCtx.lineWidth = 1;
            dotCtx.stroke();
          }
        }
      }
    }

    function animate(): void {
      frame += 1;

      // Povremeno osveži boje da uhvati promenu domena.
      if (frame % 30 === 0) {
        refreshColors();
      }

      drawSpots();
      drawDots();

      raf = window.requestAnimationFrame(animate);
    }

    animate();

    return () => {
      window.cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, [active]);

  if (!active) {
    return null;
  }

  const rootClassName = [
    "ambient-bg",
    settings.keepImage ? "ambient-bg--over-image" : "",
    revealed ? "is-revealed" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div aria-hidden="true" className={rootClassName} data-testid="ambient-bg">
      <canvas className="ambient-bg-spots" ref={spotCanvasRef} />
      <canvas className="ambient-bg-dots" ref={dotCanvasRef} />
    </div>
  );
}

export default AmbientBackground;
