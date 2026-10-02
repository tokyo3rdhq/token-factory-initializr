import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppTheme } from "@tokyo3rdhq/magi-design-system";

// 1. Design-system foundation (tokens, components, focus rings).
//    Consumes CSS custom properties defined by the package — no local copies.
import "@tokyo3rdhq/magi-design-system/styles.css";

// 2. Product-specific additions (model-list, meta-grid, topbar, footer).
//    Only styles that have no design-system equivalent live here.
import "./styles.css";

import { App } from "./App";
import { HomePage } from "./pages/Home";
import { BrowsePage } from "./pages/Browse";
import { GeneratePage } from "./pages/Generate";
import { SelectionProvider } from "./components/SelectionContext";
import { I18nProvider } from "./I18nProvider";
import { Provider as InitializrProvider } from "./initializr/InitializrContext";

// Read the theme the FOUC script already stamped on <html>. Passing
// it into <AppTheme theme=...> avoids a one-frame theme flip on
// hydration when the resolved theme differs from AppTheme's default
// (dark). The CSS attribute is the single source of truth — both
// the FOUC script and AppTheme write the same value.
function readInitialTheme(): "dark" | "light" {
  if (typeof document === "undefined") return "dark";
  const attr = document.documentElement.getAttribute("data-magi-theme");
  return attr === "light" ? "light" : "dark";
}

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("missing #root element");
}

createRoot(rootEl).render(
  <StrictMode>
    {/*
      AppTheme scopes the cyan accent to this product only.
      Default MAGI accent is green; we override with `accent="cyan"`.
      data-magi-app on <body> is set in index.html.

      The `theme` prop must match the FOUC-stamped attribute exactly,
      otherwise the resolved theme would flip on hydration. We read
      it from the DOM in `readInitialTheme()` above so the two stay
      in sync.

      Renamed from ProductTheme in @tokyo3rdhq/magi-design-system@0.3.0.
    */}
    <AppTheme accent="cyan" name="token-factory-initializr" theme={readInitialTheme()}>
      <I18nProvider>
        <InitializrProvider>
          <BrowserRouter>
            <SelectionProvider>
              <Routes>
                <Route path="/" element={<App />}>
                  <Route index element={<HomePage />} />
                  <Route path="browse" element={<BrowsePage />} />
                  <Route path="generate" element={<GeneratePage />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Route>
              </Routes>
            </SelectionProvider>
          </BrowserRouter>
        </InitializrProvider>
      </I18nProvider>
    </AppTheme>
  </StrictMode>,
);
