import { useEffect } from "react";

import { useCoreSetting, useCoreStringSetting } from "./useCoreSetting";


// ==========          KONTROLA POZADINSKE SLIKE          ==========
/*
 * Bira i pali/gasi pozadinsku sliku celog prozora (body.core-dashboard-active).
 * Vrednost se pamti u localStorage i primenjuje preko CSS promenljive
 * `--core-bg-image` na <body>, pa App.css je čita:
 *   background-image: linear-gradient(...), var(--core-bg-image, url("/<domen>-bg"));
 * Kad je slika ugašena, sloj postaje `none` (ostaje samo preliv/boja).
 */

export type ThemeBackground = { id: string; label: string; url: string };

/** Slika sakrivena (samo puna boja/preliv). */
export const BG_HIDDEN_KEY = "core.theme.bg.hidden";
/** Izabrana slika (url) kad domen ima više opcija. */
export const BG_CHOICE_KEY = "core.theme.bg.choice";

export type BackgroundControls = {
  hidden: boolean;
  setHidden: (next: boolean) => void;
  choice: string;
  setChoice: (url: string) => void;
};

/** Razreši aktivni url iz izbora (sa fallback-om na prvu ponuđenu sliku). */
export function resolveBackgroundUrl(
  backgrounds: ThemeBackground[],
  choice: string,
): string {
  if (backgrounds.some((b) => b.url === choice)) {
    return choice;
  }
  return backgrounds[0]?.url ?? "";
}

export function useBackgroundControl(
  backgrounds: ThemeBackground[],
): BackgroundControls {
  const fallback = backgrounds[0]?.url ?? "";
  const [hidden, setHidden] = useCoreSetting(BG_HIDDEN_KEY, false);
  const [choice, setChoice] = useCoreStringSetting(BG_CHOICE_KEY, fallback);

  const activeUrl = resolveBackgroundUrl(backgrounds, choice);

  useEffect(() => {
    if (typeof document === "undefined" || !document.body) {
      return;
    }
    const body = document.body;
    body.classList.toggle("core-bg-off", hidden);
    body.style.setProperty(
      "--core-bg-image",
      hidden ? "none" : `url("${activeUrl}")`,
    );
  }, [hidden, activeUrl]);

  return { hidden, setHidden, choice, setChoice };
}
