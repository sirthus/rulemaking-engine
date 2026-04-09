import { useEffect, useState } from "react";
import type { InsightReport } from "../models";
import { loadInsightReport } from "../snapshot";
import type { LoadState } from "./useAsyncData";

export function useDocketInsightStates(docketIds: string[]): Record<string, LoadState<InsightReport | null>> {
  const [states, setStates] = useState<Record<string, LoadState<InsightReport | null>>>({});

  useEffect(() => {
    let cancelled = false;
    setStates(Object.fromEntries(docketIds.map((docketId) => [docketId, { status: "loading" }])));

    for (const docketId of docketIds) {
      loadInsightReport(docketId)
        .then((data) => {
          if (!cancelled) {
            setStates((current) => ({ ...current, [docketId]: { status: "ready", data } }));
          }
        })
        .catch((error: unknown) => {
          if (!cancelled) {
            setStates((current) => ({
              ...current,
              [docketId]: { status: "error", error: error instanceof Error ? error.message : String(error) },
            }));
          }
        });
    }

    return () => {
      cancelled = true;
    };
  }, [docketIds.join("|")]);

  return states;
}
