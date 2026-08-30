import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./index.css";
import "./ReviewQueue.css";

import WorkspaceApp from "./WorkspaceApp.jsx";
import {
  registerServiceWorker,
} from "./registerServiceWorker.js";


createRoot(
  document.getElementById("root")
).render(
  <StrictMode>
    <WorkspaceApp />
  </StrictMode>
);

registerServiceWorker();
