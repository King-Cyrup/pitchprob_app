"use client";

import Link from "next/link";
import { Check, ChevronDown, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Match, Outcome } from "@/lib/types";
import ProbabilityBar from "@/components/ProbabilityBar";
import TeamBadge from "@/components/TeamBadge";
import styles from "./ui.module.css";

const outcomeNames: Record<Outcome, string> = { H: "Home", D: "Draw", A: "Away" };

function flagText(flag: Match["flags"][number]) {
  if (flag.type === "cl_ahead") return `Champions League in ${flag.days} days`;
  return `${flag.type.replaceAll("_", " ")} in ${flag.days} days`;
}

export default function MatchRow({ match, date, onSelect }: { match: Match; date: string; onSelect: (match: Match) => void }) {
  const [expanded, setExpanded] = useState(false);
  const router = useRouter();
  const kickoff = new Date(match.kickoff_utc);
  const time = new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit", minute: "2-digit", timeZone: "UTC", hourCycle: "h23",
  }).format(kickoff);
  const displayTime = match.result ? `${match.result.home_goals}–${match.result.away_goals}` : time;

  return (
    <article className={styles.matchRow}>
      <button className={styles.rowButton} type="button" aria-expanded={expanded}
        aria-label={`${match.home} versus ${match.away}${expanded ? ", collapse details" : ", show match details"}`}
        onClick={() => {
          if (window.matchMedia("(max-width: 1023px)").matches) router.push(`/match/${match.id}`);
          else {
            setExpanded(!expanded);
            onSelect(match);
            const params = new URLSearchParams(window.location.search);
            params.set("date", date);
            params.set("selected", String(match.id));
            window.history.pushState(null, "", `/?${params.toString()}`);
          }
        }}>
        <span className={styles.rowTime}>
          <strong>{displayTime}</strong>
          <span>{match.result ? "Full time" : new Intl.DateTimeFormat("en", { month: "short", day: "numeric", timeZone: "UTC" }).format(kickoff)}</span>
        </span>
        <span className={styles.teams}>
          <span className={styles.teamLine}>
            <TeamBadge name={match.home} crest={match.home_crest} />
            <span className={styles.teamName}>{match.home}</span>
          </span>
          <span className={styles.teamLine}>
            <TeamBadge name={match.away} crest={match.away_crest} />
            <span className={styles.teamName}>{match.away}</span>
          </span>
          {match.flags.map((flag, index) => <span className={styles.neutralFlag} key={`${flag.type}-${index}`}>{flagText(flag)}</span>)}
        </span>
        <div>
          <ProbabilityBar forecast={match.forecast} outcome={match.result?.outcome} />
          {match.pick_hit !== null && (
            <span className={`${styles.resultBadge} ${match.pick_hit ? styles.hit : styles.miss}`}>
              {match.pick_hit ? <Check aria-hidden="true" /> : <X aria-hidden="true" />}
              {match.pick_hit ? "Pick right" : "Pick missed"}
            </span>
          )}
          {match.forecast && !match.result && (
            <span className={styles.pickText}>Pick: {outcomeNames[match.forecast.pick]}</span>
          )}
        </div>
        <span className={styles.rowExpand}><ChevronDown aria-hidden="true" /></span>
      </button>
      {expanded && (
        <div className={styles.expanded}>
          {match.forecast ? (
            <div className={styles.quickStats}>
              <span>Expected goals <strong>{match.forecast.xg_home.toFixed(1)}–{match.forecast.xg_away.toFixed(1)}</strong></span>
              <span>Over 2.5 <strong>{Math.round(match.forecast.p_over25 * 100)}%</strong></span>
              <span>Both teams to score <strong>{Math.round(match.forecast.p_btts * 100)}%</strong></span>
            </div>
          ) : <p>{match.note || "Forecast not available for this match."}</p>}
          <div className={styles.expandedLinks}>
            <Link className={`${styles.textLink} ${styles.selectPaneLink}`} href={`/?date=${date}&selected=${match.id}`}>Open in detail pane</Link>
            <Link className={styles.textLink} href={`/match/${match.id}`}>Full match page</Link>
          </div>
        </div>
      )}
    </article>
  );
}
