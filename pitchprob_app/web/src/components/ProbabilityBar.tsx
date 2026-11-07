import type { Forecast, Outcome } from "@/lib/types";
import styles from "./ui.module.css";

const labels: Record<Outcome, string> = { H: "Home", D: "Draw", A: "Away" };

export default function ProbabilityBar({
  forecast,
  outcome,
  large = false,
}: {
  forecast: Forecast | null;
  outcome?: Outcome | null;
  large?: boolean;
}) {
  if (!forecast) {
    return <p className={styles.muted}>No forecast available.</p>;
  }

  const values: Array<{ key: Outcome; label: string; value: number }> = [
    { key: "H", label: "Home", value: forecast.p_home },
    { key: "D", label: "Draw", value: forecast.p_draw },
    { key: "A", label: "Away", value: forecast.p_away },
  ];
  const ariaLabel = values.map(({ label, value }) => `${label} ${Math.round(value * 100)}%`).join(", ");
  const resultLabel = outcome ? ` Actual result: ${labels[outcome]}.` : "";
  const resultPosition = outcome === "H"
    ? forecast.p_home / 2
    : outcome === "D"
      ? forecast.p_home + forecast.p_draw / 2
      : forecast.p_home + forecast.p_draw + forecast.p_away / 2;

  return (
    <div className={styles.probability} role="img"
      aria-label={`${ariaLabel}. Most likely: ${labels[forecast.pick]}.${resultLabel}`}>
      <div className={styles.probBarWrap}>
        <div className={styles.probBar} aria-hidden="true">
          {values.map(({ key, value }) => (
            <span
              key={key}
              className={`${styles.probSegment} ${forecast.pick === key ? styles.probSegmentPick : ""}`}
              style={{ width: `${value * 100}%` }}
            />
          ))}
        </div>
        {outcome && <span className={styles.outcomeMarker} style={{ left: `${resultPosition * 100}%` }} title={`Actual result: ${labels[outcome]}`} />}
      </div>
      <div className={`${styles.probLabels} ${large ? styles.bigProbLabels : ""}`}>
        {values.map(({ key, label, value }) => (
          <span key={key} className={forecast.pick === key ? styles.pickLabel : ""}>
            {label} <strong>{Math.round(value * 100)}%</strong>
          </span>
        ))}
      </div>
      {!outcome && <p className={styles.pickText}>Model leans {labels[forecast.pick]}</p>}
    </div>
  );
}
