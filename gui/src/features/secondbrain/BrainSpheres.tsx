import { useEffect, useRef } from "react";

import { areaColor } from "./mapsLayout";
import type { MapsArea, Sphere } from "./mapsTypes";


// ==========          SFERE — drugi sistemi na obodu prozora          ==========
// Svaki sistem (ova app + ostali sistemi) je mini-sfera: prsten podeljen po oblastima (boje kao
// na velikoj mapi), stanje online/offline i broj atoma. Aktivan sistem je u centru
// (velika mapa), ostali stoje levo/desno. Klik prebacuje centar na tu sferu.

export type SphereItem = Pick<Sphere, "id" | "label" | "online" | "total" | "areas"> & { url?: string };

type Props = {
  items: SphereItem[];
  active: string;
  onPick: (id: string) => void;
};

function MiniSphere({ areas, online }: { areas: MapsArea[]; online: boolean }) {
  const ref = useRef<HTMLCanvasElement | null>(null);
  useEffect(() => {
    const c = ref.current;
    const ctx = c?.getContext("2d");
    if (!c || !ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const S = 84;
    c.width = S * dpr; c.height = S * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, S, S);
    const cx = S / 2; const cy = S / 2;
    // sjaj
    const g = ctx.createRadialGradient(cx, cy, 4, cx, cy, S / 2);
    g.addColorStop(0, online ? "rgba(255,157,87,0.35)" : "rgba(148,163,184,0.18)");
    g.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = g; ctx.fillRect(0, 0, S, S);
    // vodilje
    ctx.strokeStyle = "rgba(148,163,184,0.2)"; ctx.lineWidth = 1;
    for (const r of [14, 24, 34]) { ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke(); }
    // segmenti po oblasti (MEMORY prsten)
    const total = areas.reduce((s, a) => s + Math.max(1, a.count), 0);
    let a0 = -Math.PI / 2;
    areas.forEach((a, i) => {
      const span = (Math.max(1, a.count) / Math.max(1, total)) * Math.PI * 2 - 0.08;
      ctx.beginPath(); ctx.arc(cx, cy, 24, a0, a0 + Math.max(0.02, span));
      ctx.strokeStyle = online ? areaColor(i) : "rgba(148,163,184,0.5)";
      ctx.lineWidth = 5; ctx.stroke();
      // tačkice na spoljnom prstenu
      const dots = Math.min(9, Math.max(1, Math.round(Math.sqrt(a.count))));
      for (let d = 0; d < dots; d += 1) {
        const ang = a0 + (span * (d + 0.5)) / dots;
        ctx.beginPath(); ctx.arc(cx + Math.cos(ang) * 34, cy + Math.sin(ang) * 34, 1.6, 0, Math.PI * 2);
        ctx.fillStyle = online ? areaColor(i) : "rgba(148,163,184,0.45)"; ctx.fill();
      }
      a0 += span + 0.08;
    });
    // jezgro
    ctx.beginPath();
    for (let i = 0; i < 6; i += 1) {
      const ang = (i * Math.PI) / 3 + Math.PI / 6;
      const px = cx + 7 * Math.cos(ang); const py = cy + 7 * Math.sin(ang);
      if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.fillStyle = online ? "#ff9d57" : "#64748b"; ctx.fill();
  }, [areas, online]);
  return <canvas className="sphere-canvas" ref={ref} style={{ width: 84, height: 84 }} />;
}

function BrainSpheres({ items, active, onPick }: Props) {
  const others = items.filter((s) => s.id !== active);
  const left = others.filter((_, i) => i % 2 === 0);
  const right = others.filter((_, i) => i % 2 === 1);
  const col = (list: SphereItem[], side: "left" | "right") => (
    <div className={`maps-spheres maps-spheres--${side}`}>
      {list.map((s) => (
        <button className={`sphere${s.online ? " is-online" : " is-offline"}`} key={s.id} onClick={() => onPick(s.id)}
          title={s.online ? `Otvori Second Brain: ${s.label}` : `${s.label} je ugašen`} type="button">
          <MiniSphere areas={s.areas} online={s.online} />
          <span className="sphere-name"><i /> {s.label}</span>
          <span className="sphere-meta">{s.online ? `${s.total} atoma` : "offline"}</span>
        </button>
      ))}
    </div>
  );
  return (
    <>
      {col(left, "left")}
      {col(right, "right")}
    </>
  );
}

export default BrainSpheres;
