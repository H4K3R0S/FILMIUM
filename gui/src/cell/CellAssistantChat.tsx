import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type ReactNode,
} from "react";

import CoreChat, {
  type ChatSuggestion,
  type CoreChatHandle,
} from "../components/chat/CoreChat";
import ChatDock, {
  ChatCollapseButton,
  ChatDockTools,
} from "../features/chat/ChatDock";
import { nextPos } from "../features/chat/chatPos";
import { chatPos, useChatFlag, useChatSetting, type ChatPos } from "../features/chat/chatPrefs";
import { askCellAssistant } from "./cellApi";


// ==========          ASISTENT/AGENT — ĆELIJA (dock + smart layout)          ==========
/*
 * Domen-agnostičan chat okvir ćelije. Zamenjuje CORE-ov `CoreAssistantChat`
 * (CoreAssistantChat vuče CODIUM, window manager, CORE podešavanja — ćelija ih
 * nema), ali ZADRŽAVA isti `ChatDock`: položaj (dole / panel desno), sklapanje
 * (minimize u lebdeće dugme) i glatke prelaze. Raspored oko chata se pomera
 * preko `onPosChange` (stranica koristi `useSmartLayout`).
 *
 * Dva moda:
 *  - bez `onSend`: generički asistent ćelije (`/cell/assistant/ask`);
 *  - sa `onSend`: domenski Agent (komanda + persona + potvrda). Domen donese
 *    `onSend`, `personaPicker` i `footer` (traka predloga); okvir ostaje isti.
 */

export type CellChatHandle = {
  /** Ubaci odgovor u nit (npr. rezultat potvrde upisa). */
  appendReply: (text: string) => void;
};

type CellAssistantChatProps = {
  /** Opseg za pamćenje položaja (npr. „kalima"); default „cell". */
  scope?: string;
  /** Naslov u sklopljenom stanju / handle-u. */
  title?: string;
  /** Klasa izgleda domena (npr. „is-kalima"). */
  variant?: string;
  /** Predlog-kartice u praznom stanju. */
  suggestions?: ChatSuggestion[];
  /** Podrazumevani položaj dok ga korisnik nije menjao. */
  defaultPos?: ChatPos;
  /** Ako je true, okvir startuje sklopljen (FILMIUM: sakriven po defaultu). */
  startCollapsed?: boolean;
  /** Domenski handler poruke (Agent komanda). Bez njega — generički asistent. */
  onSend?: (text: string) => Promise<string>;
  /** Izbor persone (uz vrh unosa). */
  personaPicker?: ReactNode;
  /** Traka ispod unosa (npr. predlog upisa „Potvrdi/Otkaži"). */
  footer?: ReactNode;
  /** Javlja stranici gde okvir STVARNO stoji (za `useSmartLayout` reflow). */
  onPosChange?: (pos: ChatPos) => void;
  /** Javlja stranici da je razgovor počeo. */
  onEngaged?: (engaged: boolean) => void;
};

const CellAssistantChat = forwardRef<CellChatHandle, CellAssistantChatProps>(
  function CellAssistantChat(
    {
      scope = "cell",
      title = "Asistent",
      variant = "",
      suggestions,
      defaultPos = "bottom",
      startCollapsed = false,
      onSend,
      personaPicker,
      footer,
      onPosChange,
      onEngaged,
    },
    ref,
  ) {
    const [pozicija, setPozicija] = useChatSetting(scope, "pos", defaultPos);
    // Glasovna podešavanja (deljena preko CORE opsega, koriste ih STT/TTS pozivi).
    const [understandLang] = useChatSetting(scope, "understandLang");
    const [speakLang] = useChatSetting(scope, "speakLang");
    const [speakVoice] = useChatSetting(scope, "speakVoice");
    const [speakReplies] = useChatFlag(scope, "voice");
    const [sklopljen, setSklopljen] = useState(startCollapsed);
    const polozaj = chatPos(pozicija);
    const chatRef = useRef<CoreChatHandle>(null);

    useImperativeHandle(ref, () => ({
      appendReply: (text: string) => chatRef.current?.appendReply(text),
    }), []);

    // ==========          SMART REFLOW (sadržaj se sklanja od docka)          ==========
    /*
     * Dock je `position: fixed` (van toka), pa sadržaj stranice ne zna za njega.
     * Ovde merimo dock i upisujemo `--cell-dock-h` (dole) ili `--cell-dock-w`
     * (desni panel) na :root; `.workspace-content` dobija odgovarajući razmak
     * (padding), pa se objekti sklanjaju ispred/pored chata umesto iza njega.
     */
    useEffect(() => {
      const root = document.documentElement;
      const nadji = () => document.querySelector<HTMLElement>(".cdock, .cdock-handle");
      const primeni = () => {
        const el = nadji();
        const h = el ? el.offsetHeight : 0;
        const w = el ? el.offsetWidth : 0;
        const dole = polozaj === "bottom";
        root.style.setProperty("--cell-dock-h", dole ? `${h}px` : "0px");
        root.style.setProperty("--cell-dock-w", dole ? "0px" : `${w}px`);
      };
      primeni();
      const el = nadji();
      const ro = el ? new ResizeObserver(primeni) : null;
      if (el && ro) {
        ro.observe(el);
      }
      return () => {
        ro?.disconnect();
        root.style.removeProperty("--cell-dock-h");
        root.style.removeProperty("--cell-dock-w");
      };
    }, [polozaj, sklopljen]);

    // Generički asistent ćelije — koristi se kad domen ne donese `onSend`.
    async function posaljiGenericki(text: string): Promise<string> {
      try {
        const odgovor = await askCellAssistant(text);
        return odgovor.sources.length > 0
          ? `${odgovor.answer}\n\nIzvori: ${odgovor.sources.join(", ")}`
          : odgovor.answer;
      } catch (error) {
        console.error("Asistent ćelije nije dostupan:", error);
        return (
          "Asistent nije dostupan u ovoj ćeliji. Proveri da li Ollama radi i da "
          + "li je model upisan u cell.json (ai.curator_model)."
        );
      }
    }

    return (
      <ChatDock
        title={title}
        variant={variant}
        pos={polozaj}
        collapsed={sklopljen}
        onExpand={() => setSklopljen(false)}
        onPosSettled={onPosChange}
      >
        <CoreChat
          ref={chatRef}
          variant={variant}
          assistantName={title}
          showModelPicker={false}
          suggestions={suggestions}
          onSend={onSend ?? posaljiGenericki}
          onEngaged={onEngaged}
          understandLang={understandLang}
          speakReplies={speakReplies}
          speakLang={speakLang}
          speakVoice={speakVoice}
          personaPicker={personaPicker}
          dockTools={(
            <ChatDockTools
              pos={polozaj}
              onCyclePos={() => setPozicija(nextPos(polozaj))}
            />
          )}
          dockCollapse={<ChatCollapseButton onCollapse={() => setSklopljen(true)} />}
          footer={footer}
        />
      </ChatDock>
    );
  },
);

export default CellAssistantChat;
