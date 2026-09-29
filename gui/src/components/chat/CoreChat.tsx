import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import {
  ArrowUp,
  Loader2,
  Mic,
  NotebookPen,
  Paperclip,
  Plus,
  Square,
  X,
} from "lucide-react";

import {
  glasDostupan,
  pustiWav,
  sintetizuj,
  snimiMikrofon,
  transkribuj,
  zaustaviGovor,
  type Snimak,
} from "../../features/voice/voiceApi";


// ==========          MODELI ZA RAZGOVOR          ==========

// ==========          MODELI PORUKA          ==========

type ChatMessage = {
  id: string;
  author: "me" | "core";
  text: string;
  files: string[];
  at: number;   // vreme nastanka (ms) — za efemerni nestanak poruke
};


// ==========          CORE CHAT POVRŠINA          ==========

/** Predlog-kartica u praznom stanju chata (klik šalje `prompt`). */
export type ChatSuggestion = {
  id: string;
  label: string;
  icon?: ReactNode;
  prompt: string;
};

type CoreChatProps = {
  // Kada je false, sakriva izbor modela (koristi se model podešen u CORE-u).
  showModelPicker?: boolean;
  // Izbornik modela iz kataloga. Ranije je ovde stajao tvrdo upisan spisak
  // („Claude", „Lokalni Qwen3.6", „ChatGPT") koji ni sa čim nije bio povezan.
  modelPicker?: ReactNode;
  // Izbornik persone, desno od izbornika modela. Stajao je uz vrh okvira, gde
  // je bez natpisa izgledao kao naslov; uz unos je tamo gde je pogled kad se
  // pise poruka.
  personaPicker?: ReactNode;
  // Alatke okvira (premesti, otkaci) — iznad polja za unos, uz gornju desnu
  // ivicu. Van okvira su izgledale kao zaseban, drugi chat.
  dockTools?: ReactNode;
  // Sakrivanje — uz ostale alatke okvira.
  dockCollapse?: ReactNode;
  // Stil okvira: domen zadrzava svoj izgled, konstrukcija je CORE-ova.
  variant?: string;
  // Traka ispod unosa (npr. trošak poslednjeg poziva).
  footer?: ReactNode;
  // Kad je dato, dodaje dugme koje trenutni unos upisuje kao belešku.
  onSaveNote?: (text: string) => void | Promise<void>;
  // Kad je dato, odgovor stiže iz backend-a (async) umesto lokalnog placeholder-a.
  onSend?: (text: string, files: string[]) => Promise<string>;
  // Predlog-kartice prikazane u praznom stanju (npr. CODIUM brze akcije).
  suggestions?: ChatSuggestion[];
  // Javlja okruženju da je razgovor počeo (ima teksta u unosu ili je poruka već
  // poslata). CODIUM dashboard na to skuplja svoje okvire u levu traku.
  onEngaged?: (engaged: boolean) => void;
  // Jezik razumevanja govora (STT): "auto"|"sr"|"en". Prazno/auto → GLAS prepozna.
  understandLang?: string;
  // Kad je true, odgovor asistenta se izgovori naglas (TTS). Podešava se u CORE.
  speakReplies?: boolean;
  // Jezik/glas izgovora (TTS). Prazno → automatski po tekstu.
  speakLang?: string;
  speakVoice?: string;
  // Ime asistenta u praznom stanju + placeholder-u. Bez njega — „CORE Assistant"
  // (CORE). Ćelija prosleđuje ime domenskog agenta (npr. „CODIUM Agent").
  assistantName?: string;
};

/**
 * Vizuelni ChatGPT-stil interfejs za CORE razgovor.
 * Bez `onSend` radi lokalno (placeholder odgovor); sa `onSend` odgovor dolazi iz
 * backend-a (npr. CODIUM asistent). Unos, balončići, fajlovi (dugme + drag&drop).
 */
function CoreChat({
  showModelPicker = true,
  modelPicker,
  personaPicker,
  dockTools,
  dockCollapse,
  variant = "",
  footer,
  onSaveNote,
  onSend,
  suggestions,
  onEngaged,
  understandLang,
  speakReplies = false,
  speakLang,
  speakVoice,
  assistantName,
}: CoreChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [attachments, setAttachments] = useState<string[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [thinking, setThinking] = useState(false);
  // Stanja glasovnog unosa: „snima" (mikrofon otvoren) i „obrada" (Whisper radi).
  const [snima, setSnima] = useState(false);
  const [glasBusy, setGlasBusy] = useState(false);
  const [glasGreska, setGlasGreska] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const dragDepth = useRef(0);
  const messageSeq = useRef(0);
  const snimakRef = useRef<Snimak | null>(null);

  // Glasovni motori postoje samo u desktop aplikaciji.
  const glasMoguc = glasDostupan();

  function nextId(): string {
    messageSeq.current += 1;
    return `msg-${messageSeq.current}`;
  }

  // ==========          AUTO-SKROL NA DNO          ==========

  // Nove poruke se pojavljuju odmah iznad unosa; istorija klizi naviše.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages, thinking]);

  // ==========          EFEMERNE PORUKE (nestaju posle ~20s)          ==========
  // Kurator chat stoji PREKO filmova — razgovor ne sme da zatrpava. Svaka poruka
  // vizuelno izbledi (CSS: `.core-chat.is-filmium .chat-bubble`, delay 20s + fade
  // 1.2s) pa se ukloni iz stanja posle fade-a. TTL ovde MORA da prati CSS.
  const ephemeral = variant.includes("is-filmium");
  useEffect(() => {
    if (!ephemeral || messages.length === 0) {
      return;
    }
    const TOTAL_MS = 21200; // 20s vidljivo + 1.2s fade (v. filmium-hub-chat.css)
    const soonest = Math.min(...messages.map((message) => message.at));
    const delay = Math.max(0, soonest + TOTAL_MS - Date.now());
    const timer = window.setTimeout(() => {
      setMessages((previous) => {
        const kept = previous.filter((message) => Date.now() - message.at < TOTAL_MS);
        return kept.length === previous.length ? previous : kept;
      });
    }, delay);
    return () => window.clearTimeout(timer);
  }, [ephemeral, messages]);

  // ==========          RAZGOVOR JE POČEO          ==========

  // „Počeo" znači: korisnik kuca ili je već poslao poruku. Prijava ide samo na
  // promenu stanja, ne na svaki otkucaj.
  const engaged = draft.trim() !== "" || messages.length > 0;

  useEffect(() => {
    onEngaged?.(engaged);
  }, [engaged, onEngaged]);


  // ==========          SLANJE PORUKE          ==========

  function appendCore(text: string): void {
    setMessages((previous) => [
      ...previous,
      { id: nextId(), author: "core", text, files: [], at: Date.now() },
    ]);
  }

  // ==========          GLASOVNI ODGOVOR (TTS)          ==========

  // Izgovara odgovor asistenta ako je glasovni odgovor uključen u podešavanjima.
  // Greška u sintezi ne sme da pokvari razgovor — odgovor je već ispisan.
  function izgovori(text: string): void {
    if (!speakReplies || !glasMoguc || text.trim() === "") {
      return;
    }
    void sintetizuj(text, speakLang, speakVoice)
      .then((wav) => pustiWav(wav))
      .catch(() => {
        /* TTS zakazao — tekst ostaje, samo bez glasa */
      });
  }

  function sendMessage(): void {
    submit(draft.trim(), attachments);
  }

  // Šalje zadati tekst (iz unosa ili predlog-kartice) kroz isti tok.
  function submit(text: string, files: string[]): void {
    const trimmed = text.trim();

    if ((trimmed === "" && files.length === 0) || thinking) {
      return;
    }

    const sentFiles = files;

    setMessages((previous) => [
      ...previous,
      {
        id: nextId(),
        author: "me",
        text: trimmed,
        files: sentFiles,
        at: Date.now(),
      },
    ]);

    setDraft("");
    setAttachments([]);

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    if (onSend) {
      // Pravi odgovor iz backend-a (async).
      setThinking(true);
      void onSend(trimmed, sentFiles)
        .then((reply) => {
          appendCore(reply);
          izgovori(reply);
        })
        .catch((error) =>
          appendCore(
            error instanceof Error
              ? `Greška: ${error.message}`
              : "Backend nije dostupan.",
          ),
        )
        .finally(() => setThinking(false));
      return;
    }

    // Jednostavan lokalni odgovor (bez backend-a, samo vizuelno).
    window.setTimeout(() => {
      appendCore(buildReply(trimmed, sentFiles));
    }, 450);
  }

  // ==========          UPIS BELEŠKE          ==========

  // Trenutni unos upisuje kao belešku (u plan za dalji razvoj) i čisti polje.
  async function saveDraftAsNote(): Promise<void> {
    const trimmed = draft.trim();
    if (trimmed === "" || !onSaveNote) {
      return;
    }
    await onSaveNote(trimmed);
    setDraft("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }

  // ==========          GLASOVNI UNOS (STT)          ==========

  // Dugme sa mikrofonom uključuje/isključuje hvatanje glasa. Zaustavljanjem se
  // snimak pošalje Whisper-u i prepoznat tekst se ODMAH pošalje asistentu —
  // isto kao da je otkucan i pritisnut Enter; korisnik samo čeka odgovor.
  // Zatečen tekst u polju se ne gubi: ide ispred izgovorenog.
  async function toggleMikrofon(): Promise<void> {
    if (glasBusy || !glasMoguc) {
      return;
    }

    // Kraj snimanja → transkripcija.
    if (snima) {
      const snimak = snimakRef.current;
      snimakRef.current = null;
      setSnima(false);
      if (!snimak) {
        return;
      }
      setGlasBusy(true);
      setGlasGreska(null);
      try {
        const wav = await snimak.stop();
        const tekst = (await transkribuj(wav, understandLang)).trim();
        if (tekst !== "") {
          // Spoji sa zatečenim tekstom u polju i pošalji odmah (kao Enter).
          const spojeno = draft.trim() === "" ? tekst : `${draft.trim()} ${tekst}`;
          submit(spojeno, attachments);
        }
      } catch (error) {
        setGlasGreska(
          error instanceof Error ? error.message : "Prepoznavanje nije uspelo.",
        );
      } finally {
        setGlasBusy(false);
      }
      return;
    }

    // Početak snimanja.
    try {
      setGlasGreska(null);
      snimakRef.current = await snimiMikrofon();
      setSnima(true);
    } catch (error) {
      snimakRef.current = null;
      setGlasGreska(
        error instanceof Error ? error.message : "Nema pristupa mikrofonu.",
      );
    }
  }

  // Gašenje okvira: prekini snimanje i zaustavi izgovor da mikrofon/zvuk ne
  // ostanu aktivni posle zatvaranja chata.
  useEffect(() => {
    return () => {
      snimakRef.current?.otkazi();
      snimakRef.current = null;
      zaustaviGovor();
    };
  }, []);

  // ==========          TASTATURA          ==========

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>): void {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }

  // ==========          AUTO-VISINA POLJA          ==========

  function handleInput(event: ChangeEvent<HTMLTextAreaElement>): void {
    setDraft(event.target.value);

    const element = event.target;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 200)}px`;
  }

  // ==========          DODAVANJE FAJLOVA          ==========

  function addFiles(files: FileList | null): void {
    const names = Array.from(files ?? []).map((file) => file.name);

    if (names.length === 0) {
      return;
    }

    setAttachments((previous) => [...previous, ...names]);
  }

  function handleFiles(event: ChangeEvent<HTMLInputElement>): void {
    addFiles(event.target.files);
    event.target.value = "";
  }

  function removeAttachment(index: number): void {
    setAttachments((previous) => previous.filter((_, i) => i !== index));
  }

  // ==========          DRAG & DROP          ==========

  function handleDragEnter(event: DragEvent<HTMLDivElement>): void {
    event.preventDefault();
    dragDepth.current += 1;

    if (event.dataTransfer.types.includes("Files")) {
      setIsDragging(true);
    }
  }

  function handleDragOver(event: DragEvent<HTMLDivElement>): void {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  }

  function handleDragLeave(event: DragEvent<HTMLDivElement>): void {
    event.preventDefault();
    dragDepth.current -= 1;

    if (dragDepth.current <= 0) {
      dragDepth.current = 0;
      setIsDragging(false);
    }
  }

  function handleDrop(event: DragEvent<HTMLDivElement>): void {
    event.preventDefault();
    dragDepth.current = 0;
    setIsDragging(false);
    addFiles(event.dataTransfer.files);
  }

  return (
    <div
      className={`core-chat ${variant} ${isDragging ? "dragging" : ""}`}
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* ==========          ISTORIJA RAZGOVORA          ========== */}

      <div className="chat-scroll">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <p className="eyebrow">{assistantName ?? "CORE Assistant"}</p>
            <h2>Kako mogu da pomognem?</h2>
            <p className="chat-empty-text">
              Postavi pitanje ili prevuci fajl da započneš razgovor.
            </p>

            {suggestions && suggestions.length > 0 && (
              <div className="chat-suggestions">
                {suggestions.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="chat-suggestion"
                    onClick={() => submit(item.prompt, [])}
                    disabled={thinking}
                  >
                    {item.icon && (
                      <span className="chat-suggestion-icon">{item.icon}</span>
                    )}
                    <span className="chat-suggestion-label">{item.label}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="chat-thread">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`chat-bubble ${message.author}`}
              >
                {message.files.length > 0 && (
                  <div className="chat-bubble-files">
                    {message.files.map((name, index) => (
                      <span key={index} className="chat-file-chip">
                        <Paperclip size={13} />
                        {name}
                      </span>
                    ))}
                  </div>
                )}

                {message.text && <p>{message.text}</p>}
              </div>
            ))}

            {thinking && (
              <div className="chat-bubble core chat-thinking" aria-live="polite">
                <span />
                <span />
                <span />
              </div>
            )}

            <div ref={bottomRef} className="chat-bottom-anchor" />
          </div>
        )}
      </div>

      {/* ==========          UNOS PORUKE (DOCK)          ========== */}

      <div className="chat-dock">
        <div className="chat-input">
          {(dockTools !== undefined || dockCollapse !== undefined) && (
            <div className="chat-dock-tools">
              {dockTools}
              {dockCollapse}
            </div>
          )}

          {attachments.length > 0 && (
            <div className="chat-attachments">
              {attachments.map((name, index) => (
                <span key={index} className="chat-file-chip">
                  <Paperclip size={13} />
                  {name}
                  <button
                    type="button"
                    className="chat-file-remove"
                    onClick={() => removeAttachment(index)}
                    aria-label="Ukloni fajl"
                  >
                    <X size={12} />
                  </button>
                </span>
              ))}
            </div>
          )}

          <textarea
            ref={textareaRef}
            className="chat-textarea"
            placeholder={`Poruka za ${assistantName ?? "CORE"}...`}
            value={draft}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            rows={1}
          />

          <div className="chat-input-row">
            <div className="chat-input-tools">
              <button
                type="button"
                className="chat-tool-button"
                onClick={() => fileInputRef.current?.click()}
                aria-label="Dodaj fajl"
              >
                <Plus size={18} />
              </button>

              <input
                ref={fileInputRef}
                type="file"
                multiple
                hidden
                onChange={handleFiles}
              />

              {onSaveNote && (
                <button
                  type="button"
                  className="chat-tool-button"
                  onClick={() => void saveDraftAsNote()}
                  disabled={draft.trim() === ""}
                  aria-label="Zabeleži u plan"
                  title="Zabeleži u plan"
                >
                  <NotebookPen size={18} />
                </button>
              )}
            </div>

            <div className="chat-input-send">
              {showModelPicker && modelPicker}
              {showModelPicker && modelPicker !== undefined
                && personaPicker !== undefined && (
                <span className="chat-picker-sep" aria-hidden="true">
                  |
                </span>
              )}
              {personaPicker}

              <button
                type="button"
                className={`chat-tool-button chat-mic ${
                  snima ? "recording" : ""
                } ${glasBusy ? "busy" : ""}`}
                onClick={() => void toggleMikrofon()}
                aria-pressed={snima}
                aria-label={
                  snima ? "Zaustavi glasovni unos" : "Glasovni unos"
                }
                title={
                  glasMoguc
                    ? glasGreska ?? (snima ? "Slušam… klikni da završiš" : "Govori umesto da kucaš")
                    : "Glasovni unos radi samo u desktop aplikaciji"
                }
                disabled={!glasMoguc || glasBusy}
              >
                {glasBusy ? (
                  <Loader2 size={18} className="chat-mic-spin" />
                ) : snima ? (
                  <Square size={16} />
                ) : (
                  <Mic size={18} />
                )}
              </button>

              <button
                type="button"
                className="chat-send-button"
                onClick={sendMessage}
                disabled={
                  thinking || (draft.trim() === "" && attachments.length === 0)
                }
                aria-label="Pošalji poruku"
              >
                <ArrowUp size={18} />
              </button>
            </div>
          </div>
        </div>

        {footer}
      </div>

      {/* ==========          DRAG OVERLAY          ========== */}

      {isDragging && (
        <div className="chat-drop-overlay" aria-hidden="true">
          <div className="chat-drop-hint">
            <Paperclip size={22} />
            <span>Pusti fajl da ga dodaš u razgovor</span>
          </div>
        </div>
      )}
    </div>
  );
}


// ==========          IKONA TIPA MODELA          ==========

/**
 * Prikazuje da li je model lokalni (procesor) ili online (oblak).
 */
// ==========          POMOĆNE FUNKCIJE          ==========

/**
 * Sastavlja jednostavan lokalni odgovor na uneti tekst i fajlove.
 * Privremeno — pravi CORE odgovor stiže sa backend integracijom.
 */
function buildReply(text: string, files: string[]): string {
  if (text === "" && files.length > 0) {
    return `Primio sam ${files.length} fajl(ova). Reci mi šta da uradim sa njima.`;
  }

  return `Razumem: "${text}". CORE je još u ranoj fazi — pravi odgovori stižu uskoro.`;
}

export default CoreChat;
