import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

const AdminApp = lazy(() => import("./AdminApp").then((module) => ({ default: module.AdminApp })));

const path = window.location.pathname.replace(/\/+$/, "") || "/";
const Root = path === "/admin" ? AdminApp : App;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Suspense fallback={<p role="status">正在打开收件箱…</p>}><Root /></Suspense>
  </StrictMode>,
);
