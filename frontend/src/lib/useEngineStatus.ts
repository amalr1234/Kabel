import { useEffect, useState } from "react";
import { api, type HealthResponse } from "@/lib/api";

export type EngineState = "checking" | HealthResponse["status"] | "offline";

export interface EngineStatus {
  state: EngineState;
  health: HealthResponse | null;
}

const POLL_MS = 30_000;
const TIMEOUT_MS = 5_000;

// One shared poller for every mounted component (sidebar + page badges).
let current: EngineStatus = { state: "checking", health: null };
const listeners = new Set<(status: EngineStatus) => void>();
let timer: ReturnType<typeof setInterval> | null = null;

async function checkEngine() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const health = await api.getHealth(controller.signal);
    current = { state: health.status, health };
  } catch {
    current = { state: "offline", health: null };
  } finally {
    clearTimeout(timeout);
  }
  listeners.forEach((listener) => listener(current));
}

function startPolling() {
  checkEngine();
  timer = setInterval(checkEngine, POLL_MS);
  window.addEventListener("focus", checkEngine);
}

function stopPolling() {
  if (timer) clearInterval(timer);
  timer = null;
  window.removeEventListener("focus", checkEngine);
}

export function useEngineStatus(): EngineStatus {
  const [status, setStatus] = useState(current);

  useEffect(() => {
    listeners.add(setStatus);
    setStatus(current);
    if (!timer) startPolling();
    return () => {
      listeners.delete(setStatus);
      if (listeners.size === 0) stopPolling();
    };
  }, []);

  return status;
}
