import Link from "next/link";
import { ArrowLeft, Check, X } from "lucide-react";
import type { Match } from "@/lib/types";
import ProbabilityBar from "@/components/ProbabilityBar";
import TeamBadge from "@/components/TeamBadge";
import styles from "./ui.module.css";

export function MatchDetailPanel({ match, compact = false }: { match: Match; compact?: boolean }) {
  const kickoff = new Date(match.kickoff_utc);
  const kickoffLabel = match.result
    ? `${match.result.home_goals}–${match.result.away_goals}`
    : new Intl.DateTimeFormat("en-GB", {
      weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
      timeZone: "UTC", hourCycle: "h23",
    }).format(kickoff);
  const pickName = match.forecast
    ? match.forecast.pick === "H" ? match.home : match.forecast.pick === "A" ? match.away : "Draw"
    : null;
  const sortedProbabilities = match.forecast
    ? [match.forecast.p_home, match.forecast.p_draw, match.forecast.p_away].sort((a, b) => b - a)
    : [];
  const lead = match.forecast ? Math.round((sortedProbabilities[0] - sortedProbabilities[1]) * 100) : null;

  return (
    <section className={styles.detailView} aria-label={`${match.home} versus ${match.away}`}>
      {!compact && (
        <Link className={styles.backLink} href="/">
          <ArrowLeft aria-hidden="true" /> Back to matches
        </Link>
      )}
      <div className={styles.detailStickyHead}>
        <div>
          <p className={styles.detailLeague}>{match.league_name}</p>
          <p className={styles.detailKickoff}>{kickoffLabel} · UTC</p>
        </div>
        {!compact && match.matchday && <span className={styles.muted}>Round {match.matchday}</span>}
      </div>

      <div className={styles.detailHero}>
        <div className={styles.detailTeams}>
          <div className={styles.detailTeam}>
            <TeamBadge name={match.home} crest={match.home_crest} large />
            <span className={styles.detailTeamName}>{match.home}</span>
          </div>
          <div className={styles.detailKickoff}>{match.result ? "Full time" : "vs"}</div>
          <div className={styles.detailTeam}>
            <TeamBadge name={match.away} crest={match.away_crest} large />
            <span className={styles.detailTeamName}>{match.away}</span>
          </div>
        </div>
        {match.forecast ? (
          <>
            <ProbabilityBar forecast={match.forecast} outcome={match.result?.outcome} large />
            <p className={styles.plainExplain}>
              The model leans {pickName}, {Math.round(match.forecast.pick_prob * 100)}%
              {lead !== null && lead > 0 ? `, ${lead} points ahead of the next outcome` : ""}.
            </p>
          </>
        ) : <p className={styles.muted}>{match.note || "No forecast available for this match."}</p>}
        {match.result && (
          <div className={styles.forecastResult}>
            <div>
              <span className={styles.statLabel}>Forecast</span>
              <strong className={styles.forecastValue}>{pickName || "Unavailable"}{match.forecast ? ` · ${Math.round(match.forecast.pick_prob * 100)}%` : ""}</strong>
            </div>
            <div>
              <span className={styles.statLabel}>Result</span>
              <strong className={styles.forecastValue}>{match.result.home_goals}–{match.result.away_goals} · {match.result.outcome === "H" ? "Home" : match.result.outcome === "A" ? "Away" : "Draw"}</strong>
            </div>
            {match.pick_hit !== null && (
              <span className={`${styles.resultBadge} ${match.pick_hit ? styles.hit : styles.miss}`}>
                {match.pick_hit ? <Check aria-hidden="true" /> : <X aria-hidden="true" />}
                {match.pick_hit ? "Pick right" : "Pick missed"}
              </span>
            )}
          </div>
        )}
      </div>

      {compact && <Link className={styles.textLink} href={`/match/${match.id}`}>Open full match page</Link>}
    </section>
  );
}
