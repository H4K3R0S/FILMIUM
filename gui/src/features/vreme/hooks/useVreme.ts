import { useContext } from "react";

import {
  VremeContext,
  type VremeContextValue,
} from "../context/VremeContext";


/**
 * Pristupa VREME kontekstu. Mora se koristiti unutar VremeProvider-a.
 */
export function useVreme(): VremeContextValue {
  const value = useContext(VremeContext);

  if (value === null) {
    throw new Error(
      "useVreme mora biti korišćen unutar <VremeProvider>.",
    );
  }

  return value;
}
