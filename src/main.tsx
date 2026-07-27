import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { DemoNoticeProvider } from "./components/DemoNotice";
import "./styles.css";
import "./mascots.css";
import "./pages.css";

const root = document.getElementById("root");

if (!root) {
  throw new Error("Root element was not found");
}

createRoot(root).render(
  <StrictMode>
    <AuthProvider>
      <DemoNoticeProvider>
        <App />
      </DemoNoticeProvider>
    </AuthProvider>
  </StrictMode>,
);
