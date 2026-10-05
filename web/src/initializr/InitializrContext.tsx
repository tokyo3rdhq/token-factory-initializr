// InitializrContext — single source of truth for the entire Phase-1
// workflow (per docs/tfi_phase_1_initializr_core_workflow.md §3 and
// §6). Replaces the older SelectionContext (selected-models only)
// by lifting the Token Factory choice into the same React context
// that already owns the selection — so the Generate action always
// sees both inputs as one unit.

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { SUPPORTED_TOKEN_FACTORIES } from "../../functions/lib/generators";
import type { InitializrState, InitializrReadiness, SelectedModel, TokenFactoryId } from "./types";

/**
 * Compute whether the current state can be sent to the generator.
 * Both must be true (per doc §9):
 *   selectedModels.length > 0  AND  tokenFactory !== null
 *
 * The caller maps the returned reason key via ``ts()`` so the
 * validator stays UI-text free.
 */
export function computeReadiness(
  state: Pick<InitializrState, "selectedModels" | "tokenFactory">,
): InitializrReadiness {
  if (state.selectedModels.length === 0) {
    return { ready: false, reason: "initializr.validation.noModels" };
  }
  if (state.tokenFactory === null) {
    return { ready: false, reason: "initializr.validation.noFactory" };
  }
  return { ready: true, reason: null };
}

interface InitializrContextValue {
  /** Current selection (selected-models only — the Token Factory
   *  choice lives on its own setter so the picker in Generate.tsx
   *  can drive it without touching the model list). */
  selectedModels: SelectedModel[];

  /** Token factory.* the user has chosen. ``null`` = not chosen. */
  tokenFactory: TokenFactoryId | null;

  /** Toggle membership for a model. Idempotent — calling twice
   *  with the same model removes it. */
  toggleModel: (ep: SelectedModel) => void;

  /** Remove a specific model from the selection (used by the
   *  "Remove" affordance on each candidate row, per doc §7). */
  removeModel: (ep: SelectedModel) => void;

  /** Set the Token Factory. */
  setTokenFactory: (id: TokenFactoryId) => void;

  /** Clear the entire selection (used after a successful generate
   *  per doc §16 — TFI stays a generator, not a project manager). */
  reset: () => void;

  /** Validation status — drives the Generate button's disabled
   *  state and the next-action hint on the empty selection state
   *  (per doc §19). */
  readiness: InitializrReadiness;
}

const InitializrContext = createContext<InitializrContextValue | null>(null);

/** Selection identity — same key as the old SelectionContext
 *  (data_source, provider, model_id) so existing call sites stay
 *  stable through the rename. */
function selectionKey(ep: SelectedModel): string {
  return `${ep.data_source}::${ep.provider}::${ep.model_id}`;
}

/**
 * Provider — wraps the app once at the root (alongside the existing
 * I18nProvider). Initial state is empty selection + null factory;
 * both are populated through user actions on Browse / Generate.
 */
export function Provider({ children }: { children: ReactNode }) {
  const [selectedModels, setSelectedModels] = useState<SelectedModel[]>([]);
  // Default to the first registered factory so the picker's visual
  // state matches the context state on initial mount. Before this,
  // the Segmented control rendered with `value ?? SUPPORTED_TOKEN_FACTORIES[0]`
  // (litellm visually) but the context stayed `null`, so the
  // Generate button was disabled until the user toggled the picker.
  const [tokenFactory, setTokenFactoryState] =
    useState<TokenFactoryId | null>(SUPPORTED_TOKEN_FACTORIES[0]);

  const toggleModel = useCallback((ep: SelectedModel) => {
    const k = selectionKey(ep);
    setSelectedModels((prev) => {
      const idx = prev.findIndex((m) => selectionKey(m) === k);
      if (idx >= 0) {
        return prev.filter((_, i) => i !== idx);
      }
      return [...prev, ep];
    });
  }, []);

  const removeModel = useCallback((ep: SelectedModel) => {
    const k = selectionKey(ep);
    setSelectedModels((prev) => prev.filter((m) => selectionKey(m) !== k));
  }, []);

  const setTokenFactory = useCallback((id: TokenFactoryId) => {
    setTokenFactoryState(id);
  }, []);

  const reset = useCallback(() => {
    setSelectedModels([]);
    setTokenFactoryState(null);
  }, []);

  const readiness = useMemo(
    () => computeReadiness({ selectedModels, tokenFactory }),
    [selectedModels, tokenFactory],
  );

  const value = useMemo<InitializrContextValue>(
    () => ({
      selectedModels,
      tokenFactory,
      toggleModel,
      removeModel,
      setTokenFactory,
      reset,
      readiness,
    }),
    [selectedModels, tokenFactory, toggleModel, removeModel, setTokenFactory, reset, readiness],
  );

  return (
    <InitializrContext.Provider value={value}>
      {children}
    </InitializrContext.Provider>
  );
}

/**
 * Hook — must be called inside an ``<InitializrProvider>``. Throws
 * on misuse so test failures surface immediately.
 */
export function useInitializr(): InitializrContextValue {
  const ctx = useContext(InitializrContext);
  if (!ctx) {
    throw new Error(
      "useInitializr must be used inside <InitializrProvider>",
    );
  }
  return ctx;
}

/** Hook — read-only selection helpers (same as the old
 *  useSelection surface — kept exported so the Browse page can
 *  read selected/clear without taking the rest of the context). */
export function useSelection() {
  const { selectedModels, toggleModel, removeModel } = useInitializr();
  const isSelected = useCallback(
    (ep: SelectedModel) =>
      selectedModels.some((m) => selectionKey(m) === selectionKey(ep)),
    [selectedModels],
  );
  return { selectedModels, toggleModel, removeModel, isSelected };
}