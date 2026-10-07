import { useEffect, useSyncExternalStore } from "react";

const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

if (typeof window !== "undefined") window.addEventListener("popstate", emit);

export function navigate(to: string, opts: { replace?: boolean } = {}) {
  if (to === location.pathname) return;
  if (opts.replace) history.replaceState(null, "", to);
  else history.pushState(null, "", to);
  emit();
}

export function usePath() {
  return useSyncExternalStore(
    (cb) => { listeners.add(cb); return () => listeners.delete(cb); },
    () => location.pathname,
  );
}

/** Splits "/create/writing/vol-24" into { state: "create", rest: "writing/vol-24" }. */
export function parsePath(path: string) {
  const parts = path.replace(/\/+$/, "").split("/").filter(Boolean);
  return { state: parts[0] ?? "create", rest: parts.slice(1).join("/") };
}

export function useTitle(title: string) {
  useEffect(() => { document.title = title; }, [title]);
}
