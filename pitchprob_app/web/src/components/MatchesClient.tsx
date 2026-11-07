"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { Match } from "@/lib/types";
import DateStrip from "@/components/DateStrip";
import { MatchDetailPanel } from "@/components/MatchDetailPanel";
import MatchGroup from "@/components/MatchGroup";
import styles from "./ui.module.css";

type League = { code: string; name: string; emblem_url: string | null };

export default function MatchesClient({
  date,
  today,
  matches,
  leagues,
  selectedLeague,
  initialSelectedMatch,
}: {
  date: string;
  today: string;
  matches: Match[];
  leagues: League[];
  selectedLeague: string;
  initialSelectedMatch: Match | null;
}) {
  const [selectedMatch, setSelectedMatch] = useState(initialSelectedMatch);
  useEffect(() => {
    setSelectedMatch(initialSelectedMatch);
  }, [initialSelectedMatch]);
  const counts = new Map<string, number>();
  for (const match of matches) counts.set(match.league, (counts.get(match.league) || 0) + 1);
  const visibleMatches = selectedLeague === "all" ? matches : matches.filter((match) => match.league === selectedLeague);
  const groups = leagues
    .filter((league) => visibleMatches.some((match) => match.league === league.code))
    .map((league) => ({
      ...league,
      matches: visibleMatches.filter((match) => match.league === league.code),
    }));
  const updatedTimes = matches.map((match) => Date.parse(match.updated_at)).filter(Number.isFinite);
  const mostRecentUpdate = updatedTimes.length ? Math.max(...updatedTimes) : null;
  const staleMinutes = mostRecentUpdate === null ? null : Math.floor((Date.now() - mostRecentUpdate) / 60_000);
  const staleMessage = staleMinutes !== null && staleMinutes > 10
    ? `Updated ${staleMinutes < 60 ? `${staleMinutes} min` : `${Math.floor(staleMinutes / 60)} hr`} ago`
    : null;

  return (
    <>
      <h1 className={styles.pageTitle}>Matches</h1>
      <DateStrip date={date} matches={matches} leagues={leagues} selectedLeague={selectedLeague} today={today} />
      <div className={styles.matchLayout}>
        <section className={styles.matchListPane} aria-label="Match list">
          <div className={styles.listHeading}>
            <h2>Fixtures</h2>
            <span>{staleMessage || `${visibleMatches.length} ${visibleMatches.length === 1 ? "match" : "matches"}`}</span>
          </div>
          {groups.length ? groups.map((group) => (
            <MatchGroup key={group.code} code={group.code} name={group.name}
              emblemUrl={group.emblem_url} matches={group.matches} date={date} onSelect={setSelectedMatch} />
          )) : (
            <div className={styles.empty}>
              <strong>No matches on this day.</strong>
              <span>Try tomorrow to see the next fixtures.</span>
              <Link className={styles.textLink} href={`/?date=${addOneDay(date)}`}>Show tomorrow’s matches</Link>
            </div>
          )}
        </section>
        <aside className={styles.detailPane} aria-label="Selected match">
          {selectedMatch ? <MatchDetailPanel match={selectedMatch} compact /> : (
            <div className={styles.detailPlaceholder}>
              <p className={styles.placeholderTitle}>Match details</p>
              <p className={styles.muted}>Select a fixture to see its match details here.</p>
            </div>
          )}
        </aside>
      </div>
      <footer className={styles.footer}>
        Times in UTC · Forecasts are statistical estimates, not betting advice. 18+ only.
      </footer>
    </>
  );
}

function addOneDay(date: string) {
  const next = new Date(`${date}T00:00:00Z`);
  next.setUTCDate(next.getUTCDate() + 1);
  return next.toISOString().slice(0, 10);
}
