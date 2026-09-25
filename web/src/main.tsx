import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import { App } from "./App";
import { HomePage } from "./pages/Home";
import { BrowsePage } from "./pages/Browse";
import { GeneratePage } from "./pages/Generate";
import { SelectionProvider } from "./components/SelectionContext";

import "./styles.css";

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("missing #root element");
}

createRoot(rootEl).render(
  <StrictMode>
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
  </StrictMode>
);