// Backward-compat shim for the legacy SelectionContext API
// (``useSelection`` returning ``selected/toggle/clear/isSelected``).
//
// The selection state has moved into the unified InitializrContext
// (per docs/tfi_phase_1_initializr_core_workflow.md §3 — there must
// be a single canonical selection state shared between Browse /
// Generate). This module re-exports the legacy ``useSelection`` so
// Browse.tsx and any other consumer continue to compile while the
// canonical state lives in InitializrContext.
//
// New code should prefer ``useInitializr`` (which exposes the full
// InitializrState, including tokenFactory). The ``useSelection`` hook
// here is the thin convenience the pre-Phase-1 codebase relied on.

import { useMemo } from "react";
import type { ModelEndpoint } from "../types";
import { useInitializr } from "../initializr/InitializrContext";

export interface SelectionStore {
  selected: ModelEndpoint[];
  toggle(ep: ModelEndpoint): void;
  clear(): void;
  isSelected(ep: ModelEndpoint): boolean;
}

function key(ep: ModelEndpoint): string {
  return `${ep.data_source}::${ep.provider}::${ep.model_id}`;
}

/** Legacy surface — reads from InitializrContext. */
export function useSelection(): SelectionStore {
  const { selectedModels, toggleModel, reset } = useInitializr();
  return useMemo<SelectionStore>(
    () => ({
      selected: selectedModels,
      toggle: toggleModel,
      clear: reset,
      isSelected: (ep: ModelEndpoint) =>
        selectedModels.some((m) => key(m) === key(ep)),
    }),
    [selectedModels, toggleModel, reset],
  );
}

/** Provider shim. The new InitializrProvider lives in
 * ``initializr/InitializrContext``; we re-export under the old name
 * so `main.tsx` doesn't have to change its import line during the
 * transition. The component itself is just an alias. */
export { Provider as SelectionProvider } from "../initializr/InitializrContext";