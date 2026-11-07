"use client";

import { ChevronDown } from "lucide-react";
import { useState } from "react";
import type { Match } from "@/lib/types";
import MatchRow from "@/components/MatchRow";
import styles from "./ui.module.css";

export default function MatchGroup({
  code,
  name,
  emblemUrl,
  matches,
  date,
  onSelect,
}: {
  code: string;
  name: string;
  emblemUrl: string | null;
  matches: Match[];
  date: string;
  onSelect: (match: Match) => void;
}) {
  const [open, setOpen] = useState(true);
  return (
    <section className={styles.leagueGroup} aria-labelledby={`league-${code}`}>
      <button className={styles.leagueToggle} id={`league-${code}`} type="button"
        aria-expanded={open} onClick={() => setOpen(!open)}>
        {emblemUrl && <img src={emblemUrl} alt="" />}
        <span className={styles.leagueName}>{name}</span>
        <span className={styles.leagueCount}>{matches.length} {matches.length === 1 ? "match" : "matches"}</span>
        <ChevronDown aria-hidden="true" />
      </button>
      {open && <div className={styles.rows}>{matches.map((match) => <MatchRow key={match.id} match={match} date={date} onSelect={onSelect} />)}</div>}
    </section>
  );
}
