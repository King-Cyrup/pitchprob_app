import Link from "next/link";
import type { MatchDetails } from "@/lib/types";
import { MatchDetailPanel } from "@/components/MatchDetailPanel";
import TeamBadge from "@/components/TeamBadge";
import styles from "./ui.module.css";

const tabs = [
  { id: "overview", label: "Overview" },
  { id: "markets", label: "Markets" },
  { id: "form", label: "Form and H2H" },
];

const leagueCountries: Record<string, string> = {
  PL: "England",
  PD: "Spain",
  SA: "Italy",
  BL1: "Germany",
  FL1: "France",
  CL: "Europe",
};

function seasonForDate(date: string) {
  const parsedDate = new Date(date);
  const startYear = parsedDate.getUTCFullYear() - (parsedDate.getUTCMonth() < 6 ? 1 : 0);
  return `${String(startYear).slice(-2)}/${String(startYear + 1).slice(-2)}`;
}

function meetingDate(date: string) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    timeZone: "UTC",
  }).format(new Date(date));
}

function FormPills({ label, form }: { label: string; form: string[] }) {
  return (
    <div className={styles.formBlock}>
      <span className={styles.statLabel}>{label}</span>
      {form.length ? (
        <div className={styles.formRow} aria-label={`${label} recent form`}>
          {form.map((result, index) => (
            <span key={`${result}-${index}`} className={`${styles.formResult} ${result === "W" ? styles.formW : result === "L" ? styles.formL : ""}`}
              title={result === "W" ? "Win" : result === "L" ? "Loss" : "Draw"}>
              {result}
            </span>
          ))}
        </div>
      ) : <p className={styles.muted}>No recent results on record.</p>}
    </div>
  );
}

export default function MatchDetailsTabs({ match, activeTab }: { match: MatchDetails; activeTab: string }) {
  const tab = tabs.some((item) => item.id === activeTab) ? activeTab : "overview";
  const h2hBySeason = new Map<string, typeof match.extras.context.h2h>();
  for (const meeting of match.extras.context.h2h) {
    const season = seasonForDate(meeting.date);
    const meetings = h2hBySeason.get(season) || [];
    meetings.push(meeting);
    h2hBySeason.set(season, meetings);
  }

  return (
    <>
      <MatchDetailPanel match={match} />
      <nav className={styles.tabs} aria-label="Match details">
        {tabs.map((item) => (
          <Link key={item.id} className={`${styles.tab} ${tab === item.id ? styles.tabActive : ""}`}
            href={`/match/${match.id}?tab=${item.id}`} aria-current={tab === item.id ? "page" : undefined}>
            {item.label}
          </Link>
        ))}
      </nav>

      {tab === "overview" && (
        <section className={styles.section} aria-labelledby="overview-heading">
          <h2 className={styles.sectionTitle} id="overview-heading">Forecast overview</h2>
          {match.forecast ? (
            <>
              <div className={styles.statGrid}>
                <div className={styles.stat}><span className={styles.statLabel}>{match.home} expected goals</span><strong className={styles.statValue}>{match.forecast.xg_home.toFixed(2)}</strong></div>
                <div className={styles.stat}><span className={styles.statLabel}>{match.away} expected goals</span><strong className={styles.statValue}>{match.forecast.xg_away.toFixed(2)}</strong></div>
                <div className={styles.stat}><span className={styles.statLabel}>Over 2.5 goals</span><strong className={styles.statValue}>{Math.round(match.forecast.p_over25 * 100)}%</strong></div>
                <div className={styles.stat}><span className={styles.statLabel}>Both teams to score</span><strong className={styles.statValue}>{Math.round(match.forecast.p_btts * 100)}%</strong></div>
              </div>
              <div className={styles.statBar}>
                <div className={styles.statBarLabel}><span>Over 2.5 goals</span><strong>{Math.round(match.forecast.p_over25 * 100)}%</strong></div>
                <div className={styles.progress}><span style={{ width: `${match.forecast.p_over25 * 100}%` }} /></div>
              </div>
            </>
          ) : <p className={styles.muted}>{match.note || "Forecast not available for this match."}</p>}
          {match.extras.scorelines.length > 0 && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>Likely scorelines</h3>
              <div className={styles.scorePills}>{match.extras.scorelines.slice(0, 5).map((score) => <span className={styles.scorePill} key={score.score}>{score.score} · {Math.round(score.p * 100)}%</span>)}</div>
            </div>
          )}
        </section>
      )}

      {tab === "markets" && (
        <section className={styles.section} aria-labelledby="markets-heading">
          <h2 className={styles.sectionTitle} id="markets-heading">Goal probabilities</h2>
          {match.forecast ? (
            <>
              {Object.entries(match.extras.goal_lines).map(([line, probability]) => (
                <div className={styles.statBar} key={line}>
                  <div className={styles.statBarLabel}><span>Over {line} goals</span><strong>{Math.round(probability * 100)}%</strong></div>
                  <div className={styles.progress}><span style={{ width: `${probability * 100}%` }} /></div>
                </div>
              ))}
              <div className={styles.statBar}>
                <div className={styles.statBarLabel}><span>Both teams to score</span><strong>{Math.round(match.forecast.p_btts * 100)}%</strong></div>
                <div className={styles.progress}><span style={{ width: `${match.forecast.p_btts * 100}%` }} /></div>
              </div>
            </>
          ) : <p className={styles.muted}>{match.note || "Market probabilities are not available."}</p>}
          {match.extras.handicap.length > 0 && (
            <table className={styles.dataTable}>
              <thead><tr><th>Line</th><th>Win</th><th>Push</th><th>Lose</th></tr></thead>
              <tbody>{match.extras.handicap.map((line) => <tr key={line.line}><td>{line.line}</td><td>{Math.round(line.win * 100)}%</td><td>{Math.round(line.push * 100)}%</td><td>{Math.round(line.lose * 100)}%</td></tr>)}</tbody>
            </table>
          )}
          <p className={styles.plainExplain}>Only probabilities produced and stored by this model are shown. No odds or bookmaker markets are included.</p>
        </section>
      )}

      {tab === "form" && (
        <section className={styles.section} aria-labelledby="form-heading">
          <h2 className={styles.sectionTitle} id="form-heading">Recent form and meetings</h2>
          <div className={styles.twoColumn}>
            <FormPills label={match.home} form={match.extras.context.form_home} />
            <FormPills label={match.away} form={match.extras.context.form_away} />
          </div>
          <div className={styles.statGrid}>
            <div className={styles.stat}><span className={styles.statLabel}>{match.home} season points per match</span><strong className={styles.statValue}>{match.extras.context.season_ppg_home?.toFixed(2) ?? "—"}</strong></div>
            <div className={styles.stat}><span className={styles.statLabel}>{match.away} season points per match</span><strong className={styles.statValue}>{match.extras.context.season_ppg_away?.toFixed(2) ?? "—"}</strong></div>
            <div className={styles.stat}><span className={styles.statLabel}>League goals per match</span><strong className={styles.statValue}>{match.extras.context.league_gpm?.toFixed(2) ?? "—"}</strong></div>
          </div>
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>Head-to-head</h3>
            {h2hBySeason.size ? (
              <div className={styles.h2hGroups}>
                {[...h2hBySeason].map(([season, meetings]) => (
                  <section className={styles.h2hGroup} key={season} aria-label={`${match.league_name} ${season}`}>
                    <header className={styles.h2hHeading}>
                      {match.league_emblem_url && <img src={match.league_emblem_url} alt="" />}
                      <div>
                        <h4 className={styles.h2hLeague}>{match.league_name} {season}</h4>
                        {leagueCountries[match.league] && <p className={styles.h2hCountry}>{leagueCountries[match.league]}</p>}
                      </div>
                    </header>
                    <div className={styles.h2hList}>
                      {meetings.map((meeting) => {
                        const homeIsMatchHome = meeting.home === match.home;
                        const homeCrest = homeIsMatchHome ? match.home_crest : match.away_crest;
                        const awayCrest = homeIsMatchHome ? match.away_crest : match.home_crest;
                        return (
                          <article className={styles.h2hCard} key={`${meeting.date}-${meeting.home}-${meeting.away}`}>
                            <div className={styles.h2hDate}>
                              <time dateTime={meeting.date}>{meetingDate(meeting.date)}</time>
                              <span>FT</span>
                            </div>
                            <div className={styles.h2hTeams}>
                              <div className={`${styles.h2hSide} ${styles.h2hHome}`}>
                                <span className={styles.h2hTeamName}>{meeting.home}</span>
                                <TeamBadge name={meeting.home} crest={homeCrest} />
                              </div>
                              <div className={styles.h2hScore} aria-label={`Final score ${meeting.score}`}>
                                {meeting.score.split("-").map((goals, index) => (
                                  <span key={index}>{goals.trim()}</span>
                                ))}
                              </div>
                              <div className={`${styles.h2hSide} ${styles.h2hAway}`}>
                                <TeamBadge name={meeting.away} crest={awayCrest} />
                                <span className={styles.h2hTeamName}>{meeting.away}</span>
                              </div>
                            </div>
                          </article>
                        );
                      })}
                    </div>
                  </section>
                ))}
              </div>
            ) : <p className={styles.muted}>No previous meetings on record.</p>}
          </div>
        </section>
      )}
    </>
  );
}
