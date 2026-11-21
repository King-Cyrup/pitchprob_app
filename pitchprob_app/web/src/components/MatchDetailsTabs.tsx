import Link from "next/link";
import { ArrowLeft, Check, X } from "lucide-react";
import type { MatchDetails, Outcome } from "@/lib/types";
import ProbabilityBar from "@/components/ProbabilityBar";
import TeamBadge from "@/components/TeamBadge";
import ValidationBadge from "@/components/ValidationBadge";
import styles from "./ui.module.css";

export const DETAIL_TABS = [
  { id: "overview", label: "Overview" },
  { id: "goals", label: "Goals" },
  { id: "correct-score", label: "Correct score" },
  { id: "corners", label: "Corners" },
  { id: "form", label: "Form and H2H" },
] as const;

export type DetailTabId = (typeof DETAIL_TABS)[number]["id"];

const outcomeNames: Record<Outcome, string> = { H: "Home", D: "Draw", A: "Away" };

function percent(value: number | null | undefined) {
  return value === null || value === undefined ? "—" : `${Math.round(value * 100)}%`;
}

function number(value: number | null | undefined, digits = 2) {
  return value === null || value === undefined ? "—" : value.toFixed(digits);
}

function kickoffLabel(kickoff: string) {
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
    timeZone: "UTC", hourCycle: "h23",
  }).format(new Date(kickoff));
}

function meetingDate(date: string) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit", month: "short", year: "numeric", timeZone: "UTC",
  }).format(new Date(`${date}T00:00:00Z`));
}

/** Build a tab URL whether the base path already has a query string or not. */
function tabHref(base: string, tabId: string) {
  const url = new URL(base, "http://local.invalid");
  url.searchParams.set("tab", tabId);
  return `${url.pathname}${url.search}`;
}

/** The three-segment Home / Draw / Away bar used in the Overview tab. */
function OutcomeBar({ match }: { match: MatchDetails }) {
  const forecast = match.forecast;
  if (!forecast) return null;
  const segments: Array<{ key: Outcome; label: string; value: number }> = [
    { key: "H", label: match.home.name, value: forecast.p_home },
    { key: "D", label: "Draw", value: forecast.p_draw },
    { key: "A", label: match.away.name, value: forecast.p_away },
  ];
  const ariaLabel = segments
    .map((s) => `${s.key === "H" ? "Home" : s.key === "A" ? "Away" : "Draw"} ${Math.round(s.value * 100)}%`)
    .join(", ");
  const result = match.result?.outcome;

  return (
    <div className={styles.outcomeBar} role="img" aria-label={`${ariaLabel}. Most likely: ${outcomeNames[forecast.pick]}.`}>
      <div className={styles.outcomeBarTrack}>
        {segments.map((segment) => (
          <span
            key={segment.key}
            className={`${styles.outcomeSegment} ${forecast.pick === segment.key ? styles.outcomeSegmentPick : ""}`}
            style={{ width: `${segment.value * 100}%` }}
            aria-hidden="true"
          />
        ))}
        {result && (
          <span
            className={styles.outcomeMarker}
            style={{ left: `${(result === "H" ? forecast.p_home / 2 : result === "D" ? forecast.p_home + forecast.p_draw / 2 : forecast.p_home + forecast.p_draw + forecast.p_away / 2) * 100}%` }}
            aria-hidden="true"
          />
        )}
      </div>
      <div className={styles.outcomeLabels}>
        {segments.map((segment) => (
          <span key={segment.key} className={forecast.pick === segment.key ? styles.outcomeLabelPick : ""}>
            <span className={styles.outcomeLabelName}>{segment.key === "D" ? "Draw" : segment.label}</span>
            <strong>{Math.round(segment.value * 100)}%</strong>
          </span>
        ))}
      </div>
    </div>
  );
}

/** A thin percentage bar used for the over/under ladders and the score list. */
function ThinBar({ value, highlight = false }: { value: number; highlight?: boolean }) {
  return (
    <span className={`${styles.thinBar} ${highlight ? styles.thinBarHighlight : ""}`} aria-hidden="true">
      <span style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />
    </span>
  );
}

/** The 7x7 scoreline heat map, drawn with CSS rather than a chart library. */
function ScoreGrid({ match }: { match: MatchDetails }) {
  const grid = match.correct_score.grid;
  if (!grid.length) return null;
  const size = grid.length;
  const flat = grid.flat();
  const max = Math.max(...flat, 0.0001);
  const topThree = new Set(
    [...flat]
      .map((value, index) => ({ value, index }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 3)
      .map((item) => item.index),
  );
  const topThreeCells = new Set(
    [...flat]
      .map((value, index) => ({ value, index }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 3)
      .map((item) => {
        const row = Math.floor(item.index / size);
        const column = item.index % size;
        return `${row}-${column}`;
      }),
  );

  return (
    <table className={styles.scoreGrid}>
      <caption>Correct-score probabilities. Rows are home goals, columns are away goals.</caption>
      <thead>
        <tr>
          <th scope="col">Home \ Away</th>
          {Array.from({ length: size }, (_, index) => (
            <th scope="col" key={index}>{index}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {grid.map((row, rowIndex) => (
          <tr key={rowIndex}>
            <th scope="row">{rowIndex}</th>
            {row.map((value, columnIndex) => {
              const key = `${rowIndex}-${columnIndex}`;
              const isTop = topThreeCells.has(key);
              const intensity = value / max;
              return (
                <td
                  key={columnIndex}
                  className={isTop ? styles.scoreCellTop : ""}
                  style={{ background: `color-mix(in srgb, var(--accent) ${Math.round(intensity * 70)}%, var(--surface))` }}
                  title={`${rowIndex}-${columnIndex}: ${(value * 100).toFixed(1)}%`}
                >
                  <span className={styles.scoreCellValue}>{value >= 0.01 ? `${(value * 100).toFixed(1)}` : ""}</span>
                  {isTop && <span className={styles.scoreCellTopMark} aria-hidden="true" />}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function FormPills({ label, form }: { label: string; form: string[] }) {
  return (
    <div className={styles.formBlock}>
      <span className={styles.statLabel}>{label} — last five</span>
      {form.length ? (
        <div className={styles.formRow} aria-label={`${label} recent form`}>
          {form.map((result, index) => (
            <span
              key={`${result}-${index}`}
              className={`${styles.formResult} ${result === "W" ? styles.formW : result === "L" ? styles.formL : ""}`}
              title={result === "W" ? "Win" : result === "L" ? "Loss" : "Draw"}
            >
              {result}
            </span>
          ))}
        </div>
      ) : <p className={styles.muted}>No recent results on record.</p>}
    </div>
  );
}

export default function MatchDetailsTabs({
  match,
  activeTab,
  showBackLink = true,
  linkBase,
}: {
  match: MatchDetails;
  activeTab: string;
  showBackLink?: boolean;
  /** Where the tab links point. Defaults to the standalone match page. */
  linkBase?: string;
}) {
  const tab = DETAIL_TABS.some((item) => item.id === activeTab) ? activeTab : "overview";
  const forecast = match.forecast;
  const pickName = forecast
    ? forecast.pick === "H" ? match.home.name : forecast.pick === "A" ? match.away.name : "Draw"
    : null;
  const lead = forecast?.lead_points ?? 0;

  // The outcome the model likes second best, named so the sentence can compare against it.
  const runnerUp = forecast
    ? (() => {
        const entries: Array<{ key: Outcome; label: string; value: number }> = [
          { key: "H", label: match.home.name, value: forecast.p_home },
          { key: "D", label: "the draw", value: forecast.p_draw },
          { key: "A", label: match.away.name, value: forecast.p_away },
        ];
        const others = entries.filter((entry) => entry.key !== forecast.pick);
        return others.sort((a, b) => b.value - a.value)[0];
      })()
    : null;

  return (
    <>
      <section className={styles.detailView} aria-label={`${match.home.name} versus ${match.away.name}`}>
        {showBackLink && (
          <Link className={styles.backLink} href="/">
            <ArrowLeft aria-hidden="true" /> Back to matches
          </Link>
        )}

        <header className={styles.detailStickyHead}>
          <div>
            <p className={styles.detailLeague}>
              {match.competition.name}
              {match.competition.stage ? ` · ${match.competition.stage}` : ""}
            </p>
            <p className={styles.detailKickoff}>{kickoffLabel(match.kickoff_utc)} UTC</p>
          </div>
          {match.neutral && <span className={styles.neutralFlag}>Neutral venue</span>}
        </header>

        <div className={styles.detailHero}>
          <div className={styles.detailTeams}>
            <div className={styles.detailTeam}>
              <TeamBadge name={match.home.name} crest={match.home.badge_url} large />
              <span className={styles.detailTeamName}>{match.home.name}</span>
            </div>
            <div className={styles.detailKickoff}>
              {match.result ? `${match.result.home_goals}–${match.result.away_goals}` : "vs"}
            </div>
            <div className={styles.detailTeam}>
              <TeamBadge name={match.away.name} crest={match.away.badge_url} large />
              <span className={styles.detailTeamName}>{match.away.name}</span>
            </div>
          </div>

          {forecast ? (
            <>
              <p className={styles.plainExplain}>
                The model leans {pickName}, {Math.round(forecast.pick_prob * 100)}%
                {runnerUp && lead > 0
                  ? ` against ${Math.round(runnerUp.value * 100)}% for ${runnerUp.label} (a ${lead}-point lead)`
                  : ""}.
              </p>
            </>
          ) : (
            <p className={styles.muted}>{match.note || "No forecast available for this match."}</p>
          )}

          {match.result && (
            <div className={styles.forecastResult}>
              <div>
                <span className={styles.statLabel}>Forecast</span>
                <strong className={styles.forecastValue}>
                  {pickName || "Unavailable"}{forecast ? ` · ${Math.round(forecast.pick_prob * 100)}%` : ""}
                </strong>
              </div>
              <div>
                <span className={styles.statLabel}>Result</span>
                <strong className={styles.forecastValue}>
                  {match.result.home_goals}–{match.result.away_goals} · {outcomeNames[match.result.outcome]}
                </strong>
              </div>
              {forecast && (
                <span className={`${styles.resultBadge} ${forecast.pick === match.result.outcome ? styles.hit : styles.miss}`}>
                  {forecast.pick === match.result.outcome
                    ? <Check aria-hidden="true" />
                    : <X aria-hidden="true" />}
                  {forecast.pick === match.result.outcome ? "Pick right" : "Pick missed"}
                </span>
              )}
            </div>
          )}

          {match.flags.length > 0 && (
            <div className={styles.flagRow}>
              {match.flags.map((flag, index) => (
                <span className={styles.neutralFlag} key={`${flag.type}-${index}`}>
                  {flag.type.replaceAll("_", " ")} in {flag.days} days
                </span>
              ))}
            </div>
          )}
        </div>
      </section>

      <nav className={styles.tabs} aria-label="Match details">
        {DETAIL_TABS.map((item) => (
          <Link
            key={item.id}
            className={`${styles.tab} ${tab === item.id ? styles.tabActive : ""}`}
            href={tabHref(linkBase ?? `/match/${match.id}`, item.id)}
            scroll={false}
            aria-current={tab === item.id ? "page" : undefined}
          >
            {item.label}
          </Link>
        ))}
      </nav>

      {tab === "overview" && (
        <section className={styles.section} aria-labelledby="overview-heading">
          <h2 className={styles.sectionTitle} id="overview-heading">Forecast overview</h2>
          {!forecast ? (
            <p className={styles.muted}>{match.note || "No forecast available for this match."}</p>
          ) : (
            <>
              <OutcomeBar match={match} />
              <div className={styles.keyFigures}>
                <div className={styles.keyFigure}>
                  <span className={styles.statLabel}>Expected goals</span>
                  <strong className={styles.keyFigureValue}>
                    {number(match.goals.exp_home)} – {number(match.goals.exp_away)}
                  </strong>
                  <span className={styles.keyFigureNote}>total {number(match.goals.exp_total)}</span>
                  <ValidationBadge validation={match.validation["1x2"]} market="1x2" />
                </div>
                <div className={styles.keyFigure}>
                  <span className={styles.statLabel}>Over 1.5 goals</span>
                  <strong className={styles.keyFigureValue}>{percent(forecast.over15)}</strong>
                  <ValidationBadge validation={match.validation["over15"]} market="over 1.5" />
                </div>
                <div className={styles.keyFigure}>
                  <span className={styles.statLabel}>Over 2.5 goals</span>
                  <strong className={styles.keyFigureValue}>{percent(forecast.p_over25)}</strong>
                  <ValidationBadge validation={match.validation["over25"]} market="over 2.5" />
                </div>
                <div className={styles.keyFigure}>
                  <span className={styles.statLabel}>Both teams to score</span>
                  <strong className={styles.keyFigureValue}>{percent(forecast.p_btts)}</strong>
                  <ValidationBadge validation={match.validation["btts"]} market="both teams to score" />
                </div>
              </div>
            </>
          )}
        </section>
      )}

      {tab === "goals" && (
        <section className={styles.section} aria-labelledby="goals-heading">
          <h2 className={styles.sectionTitle} id="goals-heading">Goals</h2>
          {!forecast || !match.goals.over["2.5"] ? (
            <p className={styles.muted}>Goal probabilities are not available for this match.</p>
          ) : (
            <>
              <div className={styles.expectedGoals}>
                <div className={styles.expectedSide}>
                  <span className={styles.statLabel}>{match.home.name}</span>
                  <strong className={styles.expectedValue}>{number(match.goals.exp_home)}</strong>
                </div>
                <span className={styles.expectedTotal}>
                  total {number(match.goals.exp_total)}
                </span>
                <div className={styles.expectedSide}>
                  <span className={styles.statLabel}>{match.away.name}</span>
                  <strong className={styles.expectedValue}>{number(match.goals.exp_away)}</strong>
                </div>
              </div>

              <h3 className={styles.subsectionTitle}>Over and under</h3>
              <div className={styles.ladder}>
                {["0.5", "1.5", "2.5", "3.5", "4.5"].map((line) => {
                  const over = match.goals.over[line];
                  if (over === undefined) return null;
                  const highlight = line === "1.5" || line === "2.5";
                  return (
                    <div className={`${styles.ladderRow} ${highlight ? styles.ladderRowHighlight : ""}`} key={line}>
                      <span className={styles.ladderLabel}>Over {line}</span>
                      <ThinBar value={over} highlight={highlight} />
                      <span className={styles.ladderValue}>{Math.round(over * 100)}%</span>
                      <span className={styles.ladderUnder}>{Math.round((1 - over) * 100)}% under</span>
                    </div>
                  );
                })}
              </div>

              <h3 className={styles.subsectionTitle}>Both teams to score</h3>
              <div className={styles.statBar}>
                <div className={styles.statBarLabel}>
                  <span>Both teams score</span>
                  <strong>{percent(match.goals.btts)}</strong>
                </div>
                <div className={styles.progress}><span style={{ width: `${(match.goals.btts ?? 0) * 100}%` }} /></div>
              </div>

              <p className={styles.plainExplain}>From the model&apos;s scoreline probabilities.</p>
            </>
          )}
        </section>
      )}

      {tab === "correct-score" && (
        <section className={styles.section} aria-labelledby="score-heading">
          <h2 className={styles.sectionTitle} id="score-heading">Correct score</h2>
          {!match.correct_score.top.length ? (
            <p className={styles.muted}>Correct-score probabilities are not available for this match.</p>
          ) : (
            <>
              <h3 className={styles.subsectionTitle}>Most likely scores</h3>
              <ol className={styles.scoreList}>
                {match.correct_score.top.slice(0, 5).map((score) => (
                  <li className={styles.scoreRow} key={score.score}>
                    <span className={styles.scoreName}>{score.score}</span>
                    <ThinBar value={score.p} />
                    <span className={styles.scoreValue}>{Math.round(score.p * 100)}%</span>
                  </li>
                ))}
              </ol>

              {match.correct_score.grid.length > 0 && (
                <>
                  <h3 className={styles.subsectionTitle}>Score table</h3>
                  <ScoreGrid match={match} />
                  {match.correct_score.grid_other !== null && (
                    <p className={styles.gridNote}>Other scores: {(match.correct_score.grid_other * 100).toFixed(1)}%</p>
                  )}
                </>
              )}

              <div className={styles.badgeRow}>
                <ValidationBadge validation={match.validation["correct_score"]} market="correct score" />
              </div>

              {match.correct_score.top[0].p < 0.2 && (
                <p className={styles.plainExplain}>
                  No score is likely: even the top one is below 20%.
                </p>
              )}
            </>
          )}
        </section>
      )}

      {tab === "corners" && (
        <section className={styles.section} aria-labelledby="corners-heading">
          <h2 className={styles.sectionTitle} id="corners-heading">Corners</h2>
          {!match.corners.available ? (
            <div className={styles.calmEmpty}>
              <p className={styles.muted}>
                {match.corners.reason || "Corner data is not available for this competition."}
              </p>
            </div>
          ) : (
            <>
              {match.corners.expected && (
                <>
                  <h3 className={styles.subsectionTitle}>Expected corners</h3>
                  <div className={styles.cornerExpected}>
                    <div className={styles.expectedSide}>
                      <span className={styles.statLabel}>{match.home.name}</span>
                      <strong className={styles.expectedValue}>{number(match.corners.expected.home, 1)}</strong>
                    </div>
                    <span className={styles.expectedTotal}>total {number(match.corners.expected.total, 1)}</span>
                    <div className={styles.expectedSide}>
                      <span className={styles.statLabel}>{match.away.name}</span>
                      <strong className={styles.expectedValue}>{number(match.corners.expected.away, 1)}</strong>
                    </div>
                  </div>
                </>
              )}

              {match.corners.total_over && (
                <>
                  <h3 className={styles.subsectionTitle}>Total corners</h3>
                  <div className={styles.chipRow}>
                    {Object.entries(match.corners.total_over).map(([line, probability]) => (
                      <span className={styles.cornerChip} key={line}>
                        Over {line} <strong>{Math.round(probability * 100)}%</strong>
                      </span>
                    ))}
                  </div>
                </>
              )}

              {match.corners.team_over && (
                <>
                  <h3 className={styles.subsectionTitle}>Each team</h3>
                  <div className={styles.twoColumn}>
                    {(["home", "away"] as const).map((side) => (
                      <div className={styles.cornerSideCard} key={side}>
                        <h4 className={styles.cornerSideTitle}>
                          {side === "home" ? match.home.name : match.away.name}
                        </h4>
                        {Object.entries(match.corners.team_over![side]).map(([line, probability]) => (
                          <div className={styles.cornerTeamRow} key={line}>
                            <span>Over {line}</span>
                            <ThinBar value={probability} />
                            <strong>{Math.round(probability * 100)}%</strong>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                </>
              )}

              {match.corners.season_average && (
                <article className={styles.cornerCard}>
                  <h4 className={styles.cornerCardTitle}>This season: all matches</h4>
                  <div className={styles.cornerCardTable}>
                    <div className={styles.cornerCardRow}><span>Team</span><span>Matches</span><span>For</span><span>Against</span><span>Total per match</span></div>
                    {([
                      [match.home.name, match.corners.season_average.home_team],
                      [match.away.name, match.corners.season_average.away_team],
                    ] as const).map(([team, average]) => (
                      <div className={styles.cornerCardRow} key={team}>
                        <span>{team}</span>
                        <span>{average?.matches ?? "—"}</span>
                        <span>{number(average?.corners_for, 1)}</span>
                        <span>{number(average?.corners_against, 1)}</span>
                        <span>{number(average?.total_per_match, 1)}</span>
                      </div>
                    ))}
                  </div>
                </article>
              )}

              {match.corners.h2h && (
                <article className={`${styles.cornerCard} ${styles.cornerCardDistinct}`}>
                  <h4 className={styles.cornerCardTitle}>Head-to-head: last 5 meetings</h4>
                  {match.corners.h2h.meetings === 0 ? (
                    <p className={styles.muted}>No earlier meetings with corner data.</p>
                  ) : (
                    <>
                      <div className={styles.h2hMeetingList}>
                        {match.corners.h2h.list.map((meeting) => (
                          <div className={styles.h2hMeeting} key={`${meeting.date}-${meeting.home}-${meeting.away}`}>
                            <time dateTime={meeting.date}>{meetingDate(meeting.date)}</time>
                            <span className={styles.h2hMeetingTeams}>{meeting.home} v {meeting.away}</span>
                            <span className={styles.h2hMeetingCorners}>{meeting.corners}</span>
                          </div>
                        ))}
                      </div>
                      <div className={styles.cornerCardTable}>
                        <div className={styles.cornerCardRow}><span>Team</span><span>Average corners</span></div>
                        <div className={styles.cornerCardRow}>
                          <span>{match.home.name}</span>
                          <span>{number(match.corners.h2h.corners_for_home_team, 1)}</span>
                        </div>
                        <div className={styles.cornerCardRow}>
                          <span>{match.away.name}</span>
                          <span>{number(match.corners.h2h.corners_for_away_team, 1)}</span>
                        </div>
                        <div className={styles.cornerCardRow}>
                          <span>Total per match</span>
                          <span>{number(match.corners.h2h.total_per_match, 1)}</span>
                        </div>
                      </div>
                    </>
                  )}
                </article>
              )}

              <div className={styles.badgeRow}>
                <ValidationBadge validation={match.corners.validation} market="corners" />
              </div>
            </>
          )}
        </section>
      )}

      {tab === "form" && (
        <section className={styles.section} aria-labelledby="form-heading">
          <h2 className={styles.sectionTitle} id="form-heading">Form and H2H</h2>
          <div className={styles.twoColumn}>
            <FormPills label={match.home.name} form={match.context.form_home} />
            <FormPills label={match.away.name} form={match.context.form_away} />
          </div>
          <div className={styles.statGrid}>
            <div className={styles.stat}>
              <span className={styles.statLabel}>{match.home.name} points per match</span>
              <strong className={styles.statValue}>{number(match.context.season_ppg_home)}</strong>
            </div>
            <div className={styles.stat}>
              <span className={styles.statLabel}>{match.away.name} points per match</span>
              <strong className={styles.statValue}>{number(match.context.season_ppg_away)}</strong>
            </div>
            <div className={styles.stat}>
              <span className={styles.statLabel}>Goals per match</span>
              <strong className={styles.statValue}>{number(match.context.league_gpm)}</strong>
            </div>
          </div>

          <h3 className={styles.subsectionTitle}>Head-to-head</h3>
          {match.context.h2h.length ? (
            <div className={styles.h2hList}>
              {match.context.h2h.map((meeting) => (
                <article className={styles.h2hCard} key={`${meeting.date}-${meeting.home}-${meeting.away}`}>
                  <div className={styles.h2hDate}>
                    <time dateTime={meeting.date}>{meetingDate(meeting.date)}</time>
                    <span>FT</span>
                  </div>
                  <div className={styles.h2hTeams}>
                    <div className={`${styles.h2hSide} ${styles.h2hHome}`}>
                      <span className={styles.h2hTeamName}>{meeting.home}</span>
                    </div>
                    <div className={styles.h2hScore} aria-label={`Final score ${meeting.score}`}>
                      {meeting.score.split("-").map((goals, index) => (
                        <span key={index}>{goals.trim()}</span>
                      ))}
                    </div>
                    <div className={`${styles.h2hSide} ${styles.h2hAway}`}>
                      <span className={styles.h2hTeamName}>{meeting.away}</span>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : <p className={styles.muted}>No previous meetings on record.</p>}
        </section>
      )}
    </>
  );
}
