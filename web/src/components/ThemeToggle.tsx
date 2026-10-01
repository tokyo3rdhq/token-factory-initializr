import { useEffect, useState } from "react";
import { Monitor, Moon, Sun } from "lucide-react";

/**
 * ThemeToggle — 3-state cycle (system → dark → light → system).
 *
 * Per DS Theme contract (packages/design-system/src/foundation/
 * globals.css + docs/component-contracts.md AppTheme):
 *   - <html data-magi-theme="dark"|"light"> is the canonical CSS hook
 *     that flips every color token — set BEFORE first paint by the
 *     inline FOUC script in index.html, kept in sync here at runtime.
 *   - <html data-magi-theme-mode="system"|"dark"|"light"> carries
 *     the user's choice so the toggle icon can render the right
 *     state. Three values, never two.
 *
 * Per DS Iconography contract: generic UI icons come from Lucide.
 *
 * The first option in the cycle is "system" — the natural default
 * for a fresh visitor. One click from "system" goes to "dark"
 * (MAGI's canonical palette), the next to "light", then back to
 * "system". This matches magi-portal's ThemeToggle.astro exactly.
 *
 * The trigger icon shows the NEXT action the user can take:
 *   - mode 'system'  → Monitor (you are following the OS; click to lock)
 *   - mode 'dark'    → Sun     (you are in dark; click for light)
 *   - mode 'light'   → Moon    (you are in light; click for dark)
 *
 * OS preference handling:
 *   - When the user has chosen 'light' or 'dark', OS color-scheme
 *     changes are IGNORED (the explicit choice always wins).
 *   - When the user is in 'system' (or has never chosen), the OS
 *     flips propagate to the rendered theme.
 */
type Mode = "system" | "dark" | "light";

const STORAGE_KEY = "tfi:theme";
const MODE_ATTR = "data-magi-theme-mode";

function readInitialMode(): Mode {
  if (typeof document === "undefined") return "system";
  const attr = document.documentElement.getAttribute(MODE_ATTR);
  if (attr === "dark" || attr === "light" || attr === "system") return attr;
  // The FOUC script always sets the attribute, but fall through to
  // localStorage if it didn't run (e.g. tests).
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "dark" || stored === "light" || stored === "system") return stored;
  } catch {
    // localStorage blocked
  }
  return "system";
}

function resolveTheme(mode: Mode): "dark" | "light" {
  if (mode === "dark" || mode === "light") return mode;
  if (typeof window !== "undefined") {
    try {
      return window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";
    } catch {
      // matchMedia may be blocked; DS canonical is dark
    }
  }
  return "dark";
}

function cycle(mode: Mode): Mode {
  if (mode === "system") return "dark";
  if (mode === "dark") return "light";
  return "system";
}

export function ThemeToggle() {
  // Read the mode the FOUC script stamped on <html>. This means the
  // first React render already matches the live DOM attribute — no
  // flicker, no theme swap on hydration.
  const [mode, setMode] = useState<Mode>(readInitialMode);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onMqChange = () => {
      // Only follow OS while we're in 'system' mode — explicit
      // choices ('dark' | 'light') override OS flips.
      if (mode === "system") {
        const resolved = mq.matches ? "dark" : "light";
        document.documentElement.setAttribute("data-magi-theme", resolved);
      }
    };
    if (mq.addEventListener) {
      mq.addEventListener("change", onMqChange);
      return () => mq.removeEventListener("change", onMqChange);
    }
    // Safari < 14 fallback.
    mq.addListener(onMqChange);
    return () => mq.removeListener(onMqChange);
  }, [mode]);

  const apply = (next: Mode) => {
    setMode(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // localStorage may be blocked; the DOM mutation below is the
      // authoritative flip — we simply lose persistence.
    }
    document.documentElement.setAttribute(MODE_ATTR, next);
    document.documentElement.setAttribute("data-magi-theme", resolveTheme(next));
  };

  const onClick = () => apply(cycle(mode));

  // Icon reflects the user's CHOICE — see the docstring for the
  // mapping. Exactly one is visible at a time so the button stays
  // a fixed 14×14px square (no layout shift).
  return (
    <button
      type="button"
      className="tfi-icon-btn"
      aria-label={`Switch theme (current: ${mode})`}
      title={`Switch theme — currently ${mode}`}
      onClick={onClick}
    >
      {mode === "dark" && (
        <Sun size={14} strokeWidth={1.75} aria-hidden="true" />
      )}
      {mode === "light" && (
        <Moon size={14} strokeWidth={1.75} aria-hidden="true" />
      )}
      {mode === "system" && (
        <Monitor size={14} strokeWidth={1.75} aria-hidden="true" />
      )}
    </button>
  );
}