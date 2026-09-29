import { useEffect, useState, type ReactNode } from "react";
import { Bot, ChevronDown, ExternalLink, PanelBottom, PanelRight } from "lucide-react";

import { POS_OPIS, nextPos } from "./chatPos";
import { chatPos, type ChatPos } from "./chatPrefs";
import "../../styles/core-chat-dock.css";


// ==========          OKVIR CHATA (položaj i sklapanje)          ==========
/*
 * Ljuska oko chata: gde okvir stoji (dole u toku stranice ili kao panel uz
 * desnu ivicu), sklapanje i otkačivanje u zaseban prozor.
 *
 * Okvir NEMA svoju traku ni svoju podlogu. Ranije je imao oboje, pa je isti
 * chat izgledao kao dva različita ekrana: providan u toku stranice, a kao
 * neprozirna kartica kad se spusti dole. Sada položaj menja samo geometriju —
 * izgled ostaje isti, a alatke stoje u redu uz polje za unos.
 *
 * Ljuska ne zna ništa o razgovoru — prima ga kao sadržaj.
 */

type ChatDockProps = {
  title: string;
  pos: ChatPos;
  /** Stil okvira: domen zadrzava svoj izgled, konstrukcija je CORE-ova. */
  variant?: string;
  /** Sklopljen okvir prikazuje samo dugme za povratak. */
  collapsed?: boolean;
  onExpand?: () => void;
  /**
   * Javlja polozaj koji je STVARNO na ekranu — tek kad okvir ode sa starog
   * mesta. Ekran zato ne presloži raspored dok stara traka jos stoji (inace bi
   * se pomerila u stranu pre nego sto krene da nestaje).
   */
  onPosSettled?: (pos: ChatPos) => void;
  children: ReactNode;
};

function PosIkona({ pos }: { pos: ChatPos }) {
  return pos === "right" ? <PanelRight size={15} /> : <PanelBottom size={15} />;
}


// ==========          ALATKE OKVIRA (u redu uz unos)          ==========

type ChatDockToolsProps = {
  pos: ChatPos;
  onCyclePos: () => void;
  /** Bez nje nema dugmeta (npr. u brauzeru nema zasebnog prozora). */
  onDetach?: () => void;
};

/**
 * Premeštanje i otkačivanje — iznad polja za unos, uz gornju desnu ivicu.
 *
 * Gola ikonica, bez okvira: dugmad sa okvirom su u uglu izgledala kao zasebne
 * kontrole nekog drugog prikaza, a ne kao alatke ovog chata.
 */
export function ChatDockTools({ pos, onCyclePos, onDetach }: ChatDockToolsProps) {
  return (
    <>
      <button
        type="button"
        className="chat-dock-icon"
        onClick={onCyclePos}
        aria-label={`Premesti chat — sledeće: ${POS_OPIS[nextPos(pos)]}`}
        title={`Premesti: ${POS_OPIS[nextPos(pos)]}`}
      >
        <PosIkona pos={nextPos(pos)} />
      </button>

      {onDetach !== undefined && (
        <button
          type="button"
          className="chat-dock-icon"
          onClick={onDetach}
          aria-label="Otkači chat u zaseban prozor"
          title="Zaseban prozor"
        >
          <ExternalLink size={15} />
        </button>
      )}
    </>
  );
}

/** Sakrivanje — ispod polja za unos, uz dugme za slanje. */
export function ChatCollapseButton({ onCollapse }: { onCollapse: () => void }) {
  return (
    <button
      type="button"
      className="chat-dock-icon"
      onClick={onCollapse}
      aria-label="Sakrij chat"
      title="Sakrij"
    >
      <ChevronDown size={15} />
    </button>
  );
}


// ==========          LJUSKA          ==========

/** Koliko traje odlazak starog polozaja, pa dolazak novog (ms). */
const IZLAZ_MS = 220;
const ULAZ_MS = 320;

function ChatDock({
  title,
  pos,
  variant = "",
  collapsed = false,
  onExpand,
  onPosSettled,
  children,
}: ChatDockProps) {
  const polozaj = chatPos(pos);

  // ==========          PRELAZ IZMEDJU POLOZAJA          ==========
  /*
   * Okvir ne sme da „teleportuje" s dna na desnu ivicu: prvo odlazi sa starog
   * mesta (dole nanize, desni panel udesno), pa se pojavljuje na novom. Zato se
   * prikazani polozaj menja tek kad se izlazak zavrsi.
   */

  const [prikazan, setPrikazan] = useState<ChatPos>(polozaj);
  // Za koji položaj traje ulazna animacija. Sama faza se IZVODI: dok tražen i
  // prikazan položaj nisu isti, okvir izlazi. Ranije je efekat sinhrono palio
  // fazu izlaska, pa je jedan kadar stajao u „mirno" pre nego što krene.
  const [ulazZa, setUlazZa] = useState<ChatPos | null>(null);

  const faza: "mirno" | "izlazi" | "ulazi" =
    polozaj !== prikazan ? "izlazi" : ulazZa === prikazan ? "ulazi" : "mirno";

  useEffect(() => {
    if (polozaj === prikazan) {
      return;
    }
    const tajmer = window.setTimeout(() => {
      setPrikazan(polozaj);
      setUlazZa(polozaj);
    }, IZLAZ_MS);
    return () => window.clearTimeout(tajmer);
  }, [polozaj, prikazan]);

  useEffect(() => {
    if (faza !== "ulazi") {
      return;
    }
    const tajmer = window.setTimeout(() => setUlazZa(null), ULAZ_MS);
    return () => window.clearTimeout(tajmer);
  }, [faza]);

  useEffect(() => {
    onPosSettled?.(prikazan);
  }, [prikazan, onPosSettled]);

  const fazaKlasa =
    faza === "izlazi" ? "is-leaving" : faza === "ulazi" ? "is-entering" : "";

  if (collapsed) {
    return (
      <button
        type="button"
        className={`cdock-handle handle-${prikazan} ${variant}`}
        onClick={onExpand}
        aria-label={`Otvori ${title}`}
        title={title}
      >
        <Bot size={17} />
        <span className="cdock-handle-label">{title}</span>
      </button>
    );
  }

  return (
    <div className={`cdock pos-${prikazan} ${variant} ${fazaKlasa}`}>
      {children}
    </div>
  );
}

export default ChatDock;
