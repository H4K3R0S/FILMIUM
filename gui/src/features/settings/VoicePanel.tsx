// ==========          PODEŠAVANJA GLASA (STT/TTS preko GLAS servisa)          ==========
// Samostalan panel: jezik razumevanja/odgovora/izgovora + glas + izgovor on/off.
// Vrednosti se dele preko CORE opsega (chatPrefs); chat ih čita i prosleđuje GLAS-u.
import { CORE_SCOPE, useChatFlag, useChatSetting } from "../chat/chatPrefs";

const WRAP: React.CSSProperties = { display: "flex", flexDirection: "column", gap: 14, maxWidth: 520 };
const ROW: React.CSSProperties = { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 };
const SEL: React.CSSProperties = { padding: "6px 10px", borderRadius: 8, minWidth: 200 };

function Red({ naslov, opis, children }: { naslov: string; opis: string; children: React.ReactNode }) {
  return (
    <div style={ROW}>
      <div>
        <div style={{ fontWeight: 600 }}>{naslov}</div>
        <div style={{ fontSize: 12, opacity: 0.7 }}>{opis}</div>
      </div>
      {children}
    </div>
  );
}

function VoicePanel({ scope = CORE_SCOPE }: { scope?: string }) {
  const [razume, setRazume] = useChatSetting(scope, "understandLang");
  const [odgovor, setOdgovor] = useChatSetting(scope, "replyLang");
  const [izgovor, setIzgovor] = useChatSetting(scope, "speakLang");
  const [glasIme, setGlasIme] = useChatSetting(scope, "speakVoice");
  const [naglas, setNaglas] = useChatFlag(scope, "voice");

  return (
    <section style={WRAP}>
      <div>
        <h2 style={{ margin: 0 }}>Glas i razgovor</h2>
        <p style={{ fontSize: 13, opacity: 0.75 }}>
          Prepoznavanje govora (STT) i izgovor (TTS) idu preko GLAS servisa (:4809).
        </p>
      </div>

      <Red naslov="Jezik razumevanja" opis="Govor → tekst (auto = srpski + engleski).">
        <select style={SEL} value={razume} onChange={(e) => setRazume(e.target.value)}>
          <option value="auto">Automatski (sr + en)</option>
          <option value="sr">Srpski</option>
          <option value="en">Engleski</option>
        </select>
      </Red>

      <Red naslov="Jezik odgovora" opis="Na kom jeziku asistent odgovara.">
        <select style={SEL} value={odgovor} onChange={(e) => setOdgovor(e.target.value)}>
          <option value="en">Engleski</option>
          <option value="sr">Srpski</option>
        </select>
      </Red>

      <Red naslov="Naglas izgovaraj odgovore" opis="Uključi TTS izgovor asistentovih odgovora.">
        <input type="checkbox" checked={naglas} onChange={(e) => setNaglas(e.target.checked)} />
      </Red>

      <Red naslov="Jezik izgovora" opis="Glas za naglas izgovor.">
        <select style={SEL} value={izgovor} onChange={(e) => setIzgovor(e.target.value)}>
          <option value="auto">Prema tekstu</option>
          <option value="en">Engleski</option>
          <option value="sr">Srpski</option>
        </select>
      </Red>

      <Red naslov="Glas (TTS)" opis="Ime glasa iz GLAS /voices, ili prazno = automatski.">
        <input style={SEL} type="text" placeholder="automatski" value={glasIme}
          onChange={(e) => setGlasIme(e.target.value)} />
      </Red>
    </section>
  );
}

export default VoicePanel;
