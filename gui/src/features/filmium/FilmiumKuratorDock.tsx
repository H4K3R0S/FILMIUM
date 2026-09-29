import { useState } from "react";
import { useNavigate } from "react-router";
import { FolderHeart, Info, ListVideo, Sparkles } from "lucide-react";

import type { ChatSuggestion } from "../../components/chat/CoreChat";
import CellAssistantChat from "../../cell/CellAssistantChat";
import "../../styles/filmium-hub-chat.css";
import {
  confirmAction,
  refuteAction,
  sendCommand,
  type CuratorResult,
} from "./lib/curatorClient";


// ==========          KURATOR — GLOBALNI DOCK          ==========
/*
 * Globalni Kurator dock FILMIUM ćelije (montiran kroz `filmiumNav.AgentDock`).
 * Ime ostaje „Kurator" (stvarno ime FILMIUM agenta). Koristi deljeni
 * `CellAssistantChat` (ChatDock: dole/desno, minimize, glatki prelazi) —
 * donese komandni `onSend` (`curatorClient`) i traku predloga. **Podrazumevano
 * je SKLOPLJEN** (`startCollapsed`) — otvara se klikom na pilulu.
 *
 * `sendCommand` vraća kind answer/proposal/navigate — `navigate` navlači rutu
 * (web plejer se sam pokreće preko `state.autoplay`), `proposal` traka
 * „Potvrdi/Otkaži" (upis tek na potvrdu), `answer` u balončić.
 */

/** Brze akcije u praznom stanju chata. */
const KURATOR_SUGGESTIONS: ChatSuggestion[] = [
  {
    id: "preporuci",
    label: "Preporuči naslov",
    icon: <Sparkles size={16} />,
    prompt:
      "Preporuči mi film ili seriju za večeras — pitaj me za raspoloženje i "
      + "žanr ako treba.",
  },
  {
    id: "lista",
    label: "Napravi listu",
    icon: <ListVideo size={16} />,
    prompt: "Napravi mi tematsku listu naslova na temu koju ti dam.",
  },
  {
    id: "objasni",
    label: "Objasni naslov",
    icon: <Info size={16} />,
    prompt:
      "Objasni mi o čemu je naslov koji ti kažem — bez spojlera osim ako "
      + "izričito tražim.",
  },
  {
    id: "kolekcija",
    label: "Sredi kolekciju",
    icon: <FolderHeart size={16} />,
    prompt:
      "Pomozi mi da organizujem kolekciju — predloži kako da grupišem naslove.",
  },
];


/** Predlog koji čeka potvrdu (upis u bazu) — od poslednjeg `sendCommand`. */
type PredlogUpisa = {
  linije: string[];
  token: string | null;
  logId: string | null;
};

/** Čitljive linije `preview` objekta za traku predloga. */
function opisiPredlog(preview: Record<string, unknown> | null): string[] {
  if (preview === null) {
    return [];
  }
  const linije: string[] = [];
  const naslov = preview.title ?? preview.media_id;
  if (naslov !== undefined && naslov !== null) {
    linije.push(`Naslov: ${String(naslov)}`);
  }
  const promene = preview.changes;
  if (promene !== null && typeof promene === "object") {
    for (const [polje, vrednost] of Object.entries(promene as Record<string, unknown>)) {
      linije.push(`${polje}: ${String(vrednost)}`);
    }
  }
  for (const [kljuc, vrednost] of Object.entries(preview)) {
    if (kljuc === "title" || kljuc === "media_id" || kljuc === "changes") {
      continue;
    }
    linije.push(`${kljuc}: ${String(vrednost)}`);
  }
  return linije;
}

/** Dodaje izvore odgovoru. */
function formatOdgovor(reply: string, sources: string[]): string {
  if (sources.length === 0) {
    return reply;
  }
  return `${reply}\n\nIzvori: ${sources.join(", ")}`;
}


function FilmiumKuratorDock() {
  const [predlog, setPredlog] = useState<PredlogUpisa | null>(null);
  const [predlogBusy, setPredlogBusy] = useState(false);
  const navigate = useNavigate();

  async function posaljiKomandu(text: string): Promise<string> {
    let rezultat: CuratorResult;
    try {
      rezultat = await sendCommand(text);
    } catch (error) {
      console.error("Kurator nije dostupan:", error);
      return (
        "Kurator nije dostupan u ovoj ćeliji. Proveri da li Ollama radi i da "
        + "li je model upisan u cell.json (ai.curator_model)."
      );
    }

    if (rezultat.kind === "navigate") {
      setPredlog(null);
      const ruta = rezultat.preview?.route;
      if (typeof ruta === "string" && ruta !== "") {
        // Kurator može uz rutu da vrati filtere (media_type/genre/sort) — prosledi ih kao query,
        // pa ih list-stranica (useFilmiumFilters) primeni.
        const filteri = rezultat.preview?.filters as Record<string, unknown> | undefined;
        const qs = filteri
          ? new URLSearchParams(
              Object.entries(filteri)
                .filter(([, v]) => v != null && v !== "")
                .map(([k, v]) => [k, String(v)]),
            ).toString()
          : "";
        navigate(qs ? `${ruta}?${qs}` : ruta, { state: { autoplay: true } });
      }
      return rezultat.reply !== "" ? rezultat.reply : "Otvaram...";
    }

    if (rezultat.kind === "proposal") {
      setPredlog({
        linije: opisiPredlog(rezultat.preview),
        token: rezultat.confirm_token,
        logId: rezultat.log_id,
      });
      return rezultat.reply !== "" ? rezultat.reply : "Predlog čeka potvrdu.";
    }

    setPredlog(null);
    return formatOdgovor(rezultat.reply, rezultat.sources);
  }

  async function potvrdiPredlog(): Promise<void> {
    const token = predlog?.token;
    if (token === null || token === undefined) {
      return;
    }
    setPredlogBusy(true);
    try {
      await confirmAction(token);
    } catch (error) {
      console.error("Potvrda predloga nije uspela:", error);
    } finally {
      setPredlogBusy(false);
      setPredlog(null);
    }
  }

  async function otkaziPredlog(): Promise<void> {
    if (predlog === null) {
      return;
    }
    setPredlogBusy(true);
    try {
      await refuteAction(predlog.logId ?? undefined);
    } catch (error) {
      console.error("Otkazivanje predloga nije uspelo:", error);
    } finally {
      setPredlogBusy(false);
      setPredlog(null);
    }
  }

  return (
    <CellAssistantChat
      scope="filmium"
      title="Kurator"
      variant="is-filmium"
      startCollapsed
      suggestions={KURATOR_SUGGESTIONS}
      onSend={posaljiKomandu}
      footer={predlog !== null ? (
        <div className="filmium-kurator-proposal">
          {predlog.linije.map((linija, indeks) => (
            <p key={indeks} className="filmium-kurator-proposal-text">{linija}</p>
          ))}
          <div className="filmium-kurator-proposal-actions">
            <button
              type="button"
              className="filmium-kurator-proposal-confirm"
              onClick={() => void potvrdiPredlog()}
              disabled={predlogBusy || predlog.token === null}
            >
              Potvrdi
            </button>
            <button
              type="button"
              className="filmium-kurator-proposal-cancel"
              onClick={() => void otkaziPredlog()}
              disabled={predlogBusy}
            >
              Otkaži
            </button>
          </div>
        </div>
      ) : undefined}
    />
  );
}

export default FilmiumKuratorDock;
