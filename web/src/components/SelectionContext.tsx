import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import type { ModelEndpoint } from "../types";

/**
 * App-wide selection state: the set of endpoints the user has
 * chosen to include in the next generated config.
 *
 * We key each entry by ``(data_source, provider, model_id)`` so
 * the same endpoint can only be selected once even if the same
 * model appears under multiple providers (refactor §13 — e.g.
 * ``huggingface/novita/openai/gpt-oss-20b`` vs
 * ``huggingface/together/openai/gpt-oss-20b`` are distinct
 * endpoints).
 */
interface SelectionStore {
  selected: ModelEndpoint[];
  toggle(ep: ModelEndpoint): void;
  clear(): void;
  isSelected(ep: ModelEndpoint): boolean;
}

const SelectionContext = createContext<SelectionStore | null>(null);

function key(ep: ModelEndpoint): string {
  return `${ep.data_source}::${ep.provider}::${ep.model_id}`;
}

export function SelectionProvider({ children }: { children: ReactNode }) {
  const [selected, setSelected] = useState<ModelEndpoint[]>([]);

  const toggle = useCallback((ep: ModelEndpoint) => {
    const k = key(ep);
    setSelected((prev) => {
      const idx = prev.findIndex((e) => key(e) === k);
      if (idx >= 0) {
        return prev.filter((_, i) => i !== idx);
      }
      return [...prev, ep];
    });
  }, []);

  const clear = useCallback(() => setSelected([]), []);

  const isSelected = useCallback(
    (ep: ModelEndpoint) => selected.some((e) => key(e) === key(ep)),
    [selected]
  );

  const value = useMemo(
    () => ({ selected, toggle, clear, isSelected }),
    [selected, toggle, clear, isSelected]
  );

  return (
    <SelectionContext.Provider value={value}>
      {children}
    </SelectionContext.Provider>
  );
}

export function useSelection(): SelectionStore {
  const ctx = useContext(SelectionContext);
  if (!ctx) {
    throw new Error("useSelection must be used inside SelectionProvider");
  }
  return ctx;
}