"use client";

import { useState } from "react";
import type { InsightsResponse } from "@/lib/types";
import styles from "./ui.module.css";

export default function ThresholdExplorer({ bands }: { bands: InsightsResponse["thresholds"] }) {
  const [minimum, setMinimum] = useState(0);
  const visible = bands.filter((band) => band.from >= minimum / 100);
  const n = visible.reduce((total, band) => total + band.n, 0);
  const hits = visible.reduce((total, band) => total + band.n * band.hit_rate, 0);
  const rate = n ? hits / n : null;

  return (
    <div>
      <label className={styles.thresholdControl}>
        <span>Minimum lead</span>
        <input type="range" min="0" max="30" step="5" value={minimum}
          aria-valuetext={`${minimum} percentage points`}
          onChange={(event) => setMinimum(Number(event.target.value))} />
        <strong className={styles.thresholdOutput}>{minimum}+ pts</strong>
      </label>
      <p className={styles.thresholdSummary}>
        {n} {n === 1 ? "match" : "matches"} remain
        {rate !== null ? ` · ${Math.round(rate * 100)}% of top picks were right` : ""}
      </p>
    </div>
  );
}
