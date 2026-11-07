import Link from "next/link";
import AppHeader from "@/components/AppHeader";
import { CalibrationChart, ConfidenceChart } from "@/components/InsightsCharts";
import ThresholdExplorer from "@/components/ThresholdExplorer";
import { getInsights } from "@/lib/api";
import styles from "@/components/ui.module.css";

export default async function InsightsPage({ searchParams }: { searchParams: Promise<{ source?: string }> }) {
  const query = await searchParams;
  const source = query.source === "backtest" ? "backtest" : "live";
  const data = await getInsights(source);

  return (
    <div className={styles.pageGrid}>
      <AppHeader />
      <h1 className={styles.pageTitle}>Insights</h1>
      <nav className={styles.sourceTabs} aria-label="Choose forecast data">
        <Link className={`${styles.sourceTab} ${source === "backtest" ? styles.sourceTabActive : ""}`}
          href="/insights?source=backtest" aria-current={source === "backtest" ? "page" : undefined}>Old matches</Link>
        <Link className={`${styles.sourceTab} ${source === "live" ? styles.sourceTabActive : ""}`}
          href="/insights?source=live" aria-current={source === "live" ? "page" : undefined}>Live forecasts</Link>
      </nav>
      {!data.available ? (
        <div className={styles.empty}>
          <strong>Backtest results are not available.</strong>
          <span>{data.note}</span>
          <Link className={styles.textLink} href="/insights?source=live">View live forecasts</Link>
        </div>
      ) : data.n === 0 ? (
        <div className={styles.empty}>
          <strong>No graded live forecasts yet.</strong>
          <span>Insights appear after forecast results are recorded.</span>
          <Link className={styles.textLink} href="/">View upcoming matches</Link>
        </div>
      ) : (
        <>
          <p className={styles.insightIntro}>
            {data.n} graded live {data.n === 1 ? "forecast" : "forecasts"}. These summaries describe recorded predictions, not future outcomes.
          </p>
          {data.n < 100 && <p className={styles.smallSample}>Early sample: fewer than 100 graded matches. Treat these patterns as provisional.</p>}
          <div className={styles.insightsGrid}>
            <section className={styles.panel} aria-labelledby="confidence-heading">
              <h2 className={styles.panelTitle} id="confidence-heading">When the model says 60%, how often is it right?</h2>
              <p className={styles.panelCaption}>Pick accuracy by top-outcome confidence. Dots show average forecast confidence.</p>
              <ConfidenceChart data={data.confidence} />
            </section>

            <section className={styles.panel} aria-labelledby="lead-heading">
              <h2 className={styles.panelTitle} id="lead-heading">Does a bigger lead mean a safer pick?</h2>
              <p className={styles.panelCaption}>A lead is the top probability minus the next-highest probability.</p>
              <ThresholdExplorer bands={data.thresholds} />
              <table className={styles.chartTable}>
                <caption>Observed pick accuracy by probability lead</caption>
                <thead><tr><th>Lead</th><th>Matches</th><th>Pick accuracy</th></tr></thead>
                <tbody>{data.thresholds.map((band) => <tr key={`${band.from}-${band.to}`}><td>{Math.round(band.from * 100)}–{Math.round(band.to * 100)} points</td><td>{band.n}</td><td>{Math.round(band.hit_rate * 100)}%</td></tr>)}</tbody>
              </table>
            </section>

            <section className={styles.panel} aria-labelledby="calibration-heading">
              <h2 className={styles.panelTitle} id="calibration-heading">Are the percentages honest?</h2>
              <p className={styles.panelCaption}>Points closer to the dotted line are better calibrated.</p>
              <CalibrationChart data={data.calibration} />
            </section>

            <section className={styles.panel} aria-labelledby="comparison-heading">
              <h2 className={styles.panelTitle} id="comparison-heading">How does the model compare?</h2>
              <p className={styles.panelCaption}>Lower log loss is better. Only forecasts stored for the same graded matches are compared.</p>
              {data.comparison.length ? (
                <table className={styles.dataTable}>
                  <thead><tr><th>Forecast source</th><th>Matches</th><th>Log loss</th><th>Top picks right</th></tr></thead>
                  <tbody>{data.comparison.map((row) => <tr key={row.model}><td>{row.model}</td><td>{row.n}</td><td>{row.logloss.toFixed(3)}</td><td>{row.pick_rate === null ? "—" : `${Math.round(row.pick_rate * 100)}%`}</td></tr>)}</tbody>
                </table>
              ) : <p className={styles.muted}>There are not enough graded matches for a comparison.</p>}
            </section>

            <section className={styles.panel} aria-labelledby="goals-heading">
              <h2 className={styles.panelTitle} id="goals-heading">Goals per match by league</h2>
              <p className={styles.panelCaption}>Based on recorded completed matches in the local results history.</p>
              {data.leagues.length ? (
                <>
                  <div className={styles.leagueStats}>
                    {data.leagues.map((league) => (
                      <div className={styles.leagueStat} key={league.league}>
                        <span>{league.league_name}</span>
                        <strong>{league.goals_per_match.toFixed(2)}</strong>
                      </div>
                    ))}
                  </div>
                  <table className={styles.chartTable}>
                    <caption>Goal averages by league</caption>
                    <thead><tr><th>League</th><th>Matches</th><th>Goals per match</th></tr></thead>
                    <tbody>{data.leagues.map((league) => <tr key={league.league}><td>{league.league_name}</td><td>{league.n}</td><td>{league.goals_per_match.toFixed(2)}</td></tr>)}</tbody>
                  </table>
                </>
              ) : <p className={styles.muted}>No completed match history is available.</p>}
            </section>
          </div>
        </>
      )}
      <footer className={styles.footer}>Forecasts are statistical estimates, not betting advice. 18+ only.</footer>
    </div>
  );
}
