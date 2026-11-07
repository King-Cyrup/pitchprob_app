import type { InsightsResponse } from "@/lib/types";
import styles from "./ui.module.css";

export function ConfidenceChart({ data }: { data: InsightsResponse["confidence"] }) {
  const width = 400;
  const height = 190;
  const chartTop = 18;
  const chartBottom = 148;
  const plotHeight = chartBottom - chartTop;
  const barWidth = data.length ? Math.min(42, 260 / data.length) : 0;
  return (
    <>
      {data.length ? (
        <svg className={styles.chart} viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby="confidence-chart-title">
          <title id="confidence-chart-title">Top-pick accuracy by forecast confidence band</title>
          {[0, 0.5, 1].map((value) => {
            const y = chartBottom - value * plotHeight;
            return <g key={value}><line className={styles.chartLine} x1="42" x2="390" y1={y} y2={y} /><text className={styles.chartText} x="5" y={y + 3}>{Math.round(value * 100)}%</text></g>;
          })}
          {data.map((band, index) => {
            const center = 62 + index * 64;
            const barHeight = band.hit_rate * plotHeight;
            const confidenceY = chartBottom - band.confidence * plotHeight;
            return (
              <g key={`${band.from}-${band.to}`}>
                <rect className={styles.chartAccent} x={center - barWidth / 2} y={chartBottom - barHeight} width={barWidth} height={barHeight} rx="4" />
                <circle cx={center} cy={confidenceY} r="4" fill="var(--surface)" stroke="var(--ink)" strokeWidth="2" />
                <text className={styles.chartText} x={center} y="166" textAnchor="middle">{Math.round(band.from * 100)}–{Math.round(band.to * 100)}%</text>
              </g>
            );
          })}
        </svg>
      ) : <p className={styles.muted}>There are not enough forecasts to draw this chart.</p>}
      <table className={styles.chartTable}>
        <caption>Forecast confidence and observed top-pick accuracy</caption>
        <thead><tr><th>Confidence</th><th>Matches</th><th>Average confidence</th><th>Pick accuracy</th></tr></thead>
        <tbody>{data.map((band) => <tr key={`${band.from}-${band.to}`}><td>{Math.round(band.from * 100)}–{Math.round(band.to * 100)}%</td><td>{band.n}</td><td>{Math.round(band.confidence * 100)}%</td><td>{Math.round(band.hit_rate * 100)}%</td></tr>)}</tbody>
      </table>
    </>
  );
}

export function CalibrationChart({ data }: { data: InsightsResponse["calibration"] }) {
  const left = 42;
  const top = 14;
  const size = 230;
  return (
    <>
      {data.length ? (
        <svg className={styles.chart} viewBox="0 0 310 280" role="img" aria-labelledby="calibration-title">
          <title id="calibration-title">Forecast confidence compared with actual pick accuracy</title>
          {[0, 0.5, 1].map((value) => {
            const x = left + value * size;
            const y = top + size - value * size;
            return <g key={value}><line className={styles.chartLine} x1={x} x2={x} y1={top} y2={top + size} /><line className={styles.chartLine} x1={left} x2={left + size} y1={y} y2={y} /><text className={styles.chartText} x={x} y={top + size + 17} textAnchor="middle">{Math.round(value * 100)}%</text><text className={styles.chartText} x="5" y={y + 3}>{Math.round(value * 100)}%</text></g>;
          })}
          <line x1={left} y1={top + size} x2={left + size} y2={top} stroke="var(--muted)" strokeDasharray="4 4" />
          {data.map((point) => (
            <circle key={`${point.from}-${point.to}`} className={styles.chartPoint}
              cx={left + point.confidence * size} cy={top + size - point.hit_rate * size}
              r={Math.max(4, Math.min(9, 3 + point.n / 20))} />
          ))}
          <text className={styles.chartText} x={left + size / 2} y="276" textAnchor="middle">Average forecast confidence</text>
          <text className={styles.chartText} transform={`translate(14 ${top + size / 2}) rotate(-90)`} textAnchor="middle">Observed top-pick accuracy</text>
        </svg>
      ) : <p className={styles.muted}>There are not enough forecasts to draw this chart.</p>}
      <table className={styles.chartTable}>
        <caption>Calibration by confidence range</caption>
        <thead><tr><th>Range</th><th>Matches</th><th>Forecast</th><th>Observed</th></tr></thead>
        <tbody>{data.map((point) => <tr key={`${point.from}-${point.to}`}><td>{Math.round(point.from * 100)}–{Math.round(point.to * 100)}%</td><td>{point.n}</td><td>{Math.round(point.confidence * 100)}%</td><td>{Math.round(point.hit_rate * 100)}%</td></tr>)}</tbody>
      </table>
    </>
  );
}
