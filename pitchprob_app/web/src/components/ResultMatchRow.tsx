import Link from "next/link";
import { Check, X } from "lucide-react";
import type { Match } from "@/lib/types";
import ProbabilityBar from "@/components/ProbabilityBar";
import TeamBadge from "@/components/TeamBadge";
import styles from "./ui.module.css";

export default function ResultMatchRow({ match }: { match: Match }) {
  const hit = Boolean(match.pick_hit);
  return (
    <Link className={styles.resultRow} href={`/match/${match.id}`}>
      <div className={styles.resultTeams}>
        <span className={styles.teamLine}><TeamBadge name={match.home} crest={match.home_crest} /><span className={styles.teamName}>{match.home}</span></span>
        <span className={styles.teamLine}><TeamBadge name={match.away} crest={match.away_crest} /><span className={styles.teamName}>{match.away}</span></span>
      </div>
      <div className={styles.resultForecast}>
        <ProbabilityBar forecast={match.forecast} outcome={match.result?.outcome} />
        {match.forecast && <span className={styles.muted}>Pick: {match.forecast.pick === "H" ? match.home : match.forecast.pick === "A" ? match.away : "Draw"}</span>}
      </div>
      <strong className={styles.resultScore}>
        {match.result ? `${match.result.home_goals}–${match.result.away_goals}` : "—"}
      </strong>
      <span className={`${styles.resultBadge} ${hit ? styles.hit : styles.miss}`}>
        {hit ? <Check aria-hidden="true" /> : <X aria-hidden="true" />}
        {hit ? "Pick right" : "Pick missed"}
      </span>
    </Link>
  );
}
