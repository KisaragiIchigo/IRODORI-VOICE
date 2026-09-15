import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// フォントは同梱する。外部 CDN を参照するとオフラインで崩れる。
import "@fontsource/archivo/500.css";
import "@fontsource/archivo/600.css";
import "@fontsource/m-plus-1/300.css";
import "@fontsource/m-plus-1/400.css";
import "@fontsource/m-plus-1/500.css";
import "@fontsource/m-plus-1/700.css";
import "@fontsource/ibm-plex-mono/400.css";

import App from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
