import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ProductTheme } from "@tokyo3rdhq/magi-design-system";

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

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("missing #root element");
}

createRoot(rootEl).render(
  <StrictMode>
    {/*
      ProductTheme scopes the cyan accent to this product only.
      The default MAGI accent is green; we override with `accent="cyan"`.
      data-magi-app on <body> is set in index.html.
    */}
    <ProductTheme accent="cyan" name="token-factory-initializr">
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
    </ProductTheme>
  </StrictMode>
);
