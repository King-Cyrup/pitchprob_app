import Link from "next/link";
import AppHeader from "@/components/AppHeader";
import ResultMatchRow from "@/components/ResultMatchRow";
import { getResults, getResultsDays } from "@/lib/api";
import styles from "@/components/ui.module.css";

export default async function ResultsPage({ searchParams }: { searchParams: Promise<{ date?: string }> }) {
  const query = await searchParams;
  const days = await getResultsDays();
  const date = query.date || days[0]?.date || new Date().toISOString().slice(0, 10);
  const data = await getResults(date);

  return (
    <div className={styles.pageGrid}>
      <AppHeader />
      <h1 className={styles.pageTitle}>Results</h1>
      {days.length > 0 && (
        <nav className={styles.selectDate} aria-label="Choose a results day">
          {days.map((day) => (
            <Link key={day.date} className={`${styles.smallChip} ${date === day.date ? styles.smallChipActive : ""}`}
              href={`/results?date=${day.date}`} aria-current={date === day.date ? "date" : undefined}>
              {formatDate(day.date)} · {day.n}
            </Link>
          ))}
        </nav>
      )}
      {data.summary.n ? (
        <>
          <section className={styles.summary} aria-label="Daily forecast summary">
            <strong>{data.summary.hits} / {data.summary.n}</strong>
            <span>most likely outcomes were right</span>
          </section>
          <div className={styles.progress} role="img"
            aria-label={`${Math.round((data.summary.accuracy || 0) * 100)} percent of top picks were correct`}>
            <span style={{ width: `${(data.summary.accuracy || 0) * 100}%` }} />
          </div>
          {data.leagues.map((league) => (
            <section className={styles.resultLeague} key={league.code} aria-labelledby={`results-${league.code}`}>
              <h2 className={styles.resultLeagueHeading} id={`results-${league.code}`}>
                {league.emblem_url && <img src={league.emblem_url} alt="" />}
                <span>{league.name}</span>
                <span className={styles.leagueCount}>{league.matches.length}</span>
              </h2>
              <div>{league.matches.map((match) => <ResultMatchRow key={match.id} match={match} />)}</div>
            </section>
          ))}
        </>
      ) : (
        <div className={styles.empty}>
          <strong>No graded matches for this day.</strong>
          <span>Choose another day to review forecasts and results.</span>
          <Link className={styles.textLink} href="/">View upcoming matches</Link>
        </div>
      )}
      <footer className={styles.footer}>Forecasts are statistical estimates, not betting advice. 18+ only.</footer>
    </div>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { day: "numeric", month: "short", timeZone: "UTC" })
    .format(new Date(`${value}T00:00:00Z`));
}
