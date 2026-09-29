// ==========          POLOŽAJ CHAT OKVIRA          ==========
// Čist modul uz `ChatDock`: dve vrednosti koje i sam dock i ekrani oko njega
// čitaju. Stoje odvojeno jer fajl koji uz komponentu izvozi i nešto drugo
// gubi hot reload.
import type { ChatPos } from "./chatPrefs";

/** Drugi položaj — dva su, pa je „sledeći" ujedno i „onaj drugi". */
export function nextPos(pos: ChatPos): ChatPos {
  return pos === "bottom" ? "right" : "bottom";
}

export const POS_OPIS: Record<ChatPos, string> = {
  bottom: "Dole (u toku stranice)",
  right: "Panel desno",
};
