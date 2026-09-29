import { useCallback, useEffect, useState } from "react";


// ==========          GLOBALNO CORE PODEŠAVANJE          ==========

/*
 * Boolean/string CORE podešavanje u localStorage, REAKTIVNO: kad ga jedan
 * ekran promeni (npr. Podešavanja → Tema), svi ostali korisnici istog ključa
 * (npr. AmbientBackground) se odmah osveže. Sinhronizacija ide preko:
 *   - `storage` događaja (druge kartice/prozori), i
 *   - internog `core-setting-changed` događaja (ista kartica — `storage` se
 *     ne okida u istom dokumentu).
 * Tolerantno na nedostupan storage — pada na prosleđenu podrazumevanu vrednost.
 */

const CHANGE_EVENT = "core-setting-changed";

type ChangeDetail = { key: string; value: string };

function emitChange(key: string, value: string): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* storage nedostupan — nastavi, bar se osveži u memoriji */
  }
  window.dispatchEvent(
    new CustomEvent<ChangeDetail>(CHANGE_EVENT, { detail: { key, value } }),
  );
}

/** Zajednička pretplata na promene jednog ključa (ista + druge kartice). */
function useSettingSync(key: string, apply: (raw: string) => void): void {
  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const onCustom = (event: Event) => {
      const detail = (event as CustomEvent<ChangeDetail>).detail;
      if (detail && detail.key === key) {
        apply(detail.value);
      }
    };
    const onStorage = (event: StorageEvent) => {
      if (event.key === key && event.newValue !== null) {
        apply(event.newValue);
      }
    };
    window.addEventListener(CHANGE_EVENT, onCustom);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(CHANGE_EVENT, onCustom);
      window.removeEventListener("storage", onStorage);
    };
    // apply zavisi samo od setValue-a (stabilan); ključ je jedina prava zavisnost
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
}

export function useCoreSetting(
  key: string,
  defaultValue: boolean,
): [boolean, (next: boolean) => void] {
  const [value, setValue] = useState<boolean>(() => {
    if (typeof window === "undefined") {
      return defaultValue;
    }
    const stored = window.localStorage.getItem(key);
    return stored === null ? defaultValue : stored === "true";
  });

  useSettingSync(key, (raw) => setValue(raw === "true"));

  const update = useCallback(
    (next: boolean) => {
      setValue(next);
      emitChange(key, String(next));
    },
    [key],
  );

  return [value, update];
}


// ==========          GLOBALNO STRING PODEŠAVANJE          ==========

export function useCoreStringSetting(
  key: string,
  defaultValue: string,
): [string, (next: string) => void] {
  const [value, setValue] = useState<string>(() => {
    if (typeof window === "undefined") {
      return defaultValue;
    }
    return window.localStorage.getItem(key) ?? defaultValue;
  });

  useSettingSync(key, (raw) => setValue(raw));

  const update = useCallback(
    (next: string) => {
      setValue(next);
      emitChange(key, next);
    },
    [key],
  );

  return [value, update];
}
