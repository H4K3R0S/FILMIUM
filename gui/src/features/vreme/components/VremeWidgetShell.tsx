import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import { X } from "lucide-react";

import type { VremeTool } from "../types";
import { useVreme } from "../hooks/useVreme";
import { playSound } from "../../../lib/sound";


// ==========          OKVIR LEBDEĆEG WIDGETA          ==========

type VremeWidgetShellProps = {
  tool: VremeTool;
  title: string;
  icon: ReactNode;
  children: ReactNode;
};

/** Približna veličina widgeta za zadržavanje na ekranu. */
const MARGIN = 40;

/**
 * Ograničava vrednost na opseg.
 */
function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

/**
 * Minimalan lebdeći prozor koji se prevlači za naslovnu traku i zatvara
 * dugmetom x. Pamti poziciju u kontekstu (i localStorage) po prevlačenju.
 */
function VremeWidgetShell({
  tool,
  title,
  icon,
  children,
}: VremeWidgetShellProps) {
  const { widgets, closeWidget, moveWidget } = useVreme();
  const state = widgets[tool];

  // Prevučena pozicija pamti UZ koju spoljnu vrednost je nastala. Kad se
  // pozicija promeni spolja (drugi prozor), ključ se razlikuje i prikaz se
  // vraća na spoljnu — bez upisa iz efekta, koji je značio jedan kadar sa
  // starim mestom.
  const spoljniKljuc = `${state.x}|${state.y}`;
  const [prevuceno, setPrevuceno] = useState<{
    kljuc: string;
    x: number;
    y: number;
  } | null>(null);

  // Memoizacija nije ukras: `position` ulazi u zavisnosti efekta, a nov objekat
  // pri svakom crtanju značio bi da se efekat budi bez razloga.
  const position = useMemo(
    () => (prevuceno?.kljuc === spoljniKljuc
      ? { x: prevuceno.x, y: prevuceno.y }
      : { x: state.x, y: state.y }),
    [prevuceno, spoljniKljuc, state.x, state.y],
  );

  const setPosition = useCallback(
    (sledeca: { x: number; y: number }) => {
      setPrevuceno({ kljuc: spoljniKljuc, ...sledeca });
    },
    [spoljniKljuc],
  );
  const positionRef = useRef(position);
  // Upis ide u efekat, ne u telo crtanja: crtanje sme samo da čita ono što mu
  // je dato, a React ne obećava da će se telo izvršiti tačno jednom.
  useEffect(() => {
    positionRef.current = position;
  }, [position]);

  // Zvuk pri otvaranju widget (popup) prozora.
  useEffect(() => {
    playSound("popup");
  }, []);

  const handlePointerDown = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      event.preventDefault();

      const startX = event.clientX;
      const startY = event.clientY;
      const originX = positionRef.current.x;
      const originY = positionRef.current.y;

      const handleMove = (moveEvent: PointerEvent) => {
        const nextX = clamp(
          originX + (moveEvent.clientX - startX),
          0,
          window.innerWidth - MARGIN,
        );
        const nextY = clamp(
          originY + (moveEvent.clientY - startY),
          0,
          window.innerHeight - MARGIN,
        );

        setPosition({ x: nextX, y: nextY });
      };

      const handleUp = () => {
        window.removeEventListener("pointermove", handleMove);
        window.removeEventListener("pointerup", handleUp);
        moveWidget(tool, positionRef.current.x, positionRef.current.y);
      };

      window.addEventListener("pointermove", handleMove);
      window.addEventListener("pointerup", handleUp);
    },
    [tool, moveWidget, setPosition],
  );

  return (
    <div
      className="vreme-widget"
      style={{ left: `${position.x}px`, top: `${position.y}px` }}
    >
      <div
        className="vreme-widget-header"
        onPointerDown={handlePointerDown}
      >
        <span className="vreme-widget-title">
          {icon}
          {title}
        </span>

        <button
          aria-label={`Zatvori ${title} widget`}
          className="vreme-widget-close"
          onClick={() => closeWidget(tool)}
          onPointerDown={(event) => event.stopPropagation()}
          type="button"
        >
          <X size={15} strokeWidth={2.4} />
        </button>
      </div>

      <div className="vreme-widget-body">{children}</div>
    </div>
  );
}

export default VremeWidgetShell;
