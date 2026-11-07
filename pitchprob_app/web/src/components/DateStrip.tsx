import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { Match } from "@/lib/types";
import styles from "./ui.module.css";

function addDays(value: string, amount: number) {
  const current = new Date(`${value}T00:00:00Z`);
  current.setUTCDate(current.getUTCDate() + amount);
  return current.toISOString().slice(0, 10);
}

function labelFor(value: string, today: string) {
  const offset = Math.round((Date.parse(`${value}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / 86_400_000);
  if (offset === 0) return "Today";
  if (offset === 1) return "Tomorrow";
  return new Intl.DateTimeFormat("en", { weekday: "short", timeZone: "UTC" })
    .format(new Date(`${value}T00:00:00Z`));
}

export default function DateStrip({
  date,
  matches,
  leagues,
  selectedLeague,
  today,
}: {
  date: string;
  matches: Match[];
  leagues: Array<{ code: string; name: string; emblem_url: string | null }>;
  selectedLeague: string;
  today: string;
}) {
  const leagueCounts = new Map<string, number>();
  for (const match of matches) leagueCounts.set(match.league, (leagueCounts.get(match.league) || 0) + 1);
  const dateHref = (nextDate: string) => {
    const query = new URLSearchParams({ date: nextDate });
    if (selectedLeague !== "all") query.set("league", selectedLeague);
    return `/?${query.toString()}`;
  };
  const allLeagues = [{ code: "all", name: "All", emblem_url: null }, ...leagues];

  return (
    <div className={styles.controlStack}>
      <nav className={styles.dateStrip} aria-label="Choose match date">
        <Link className={styles.stripArrow} href={dateHref(addDays(date, -1))} aria-label="Previous day">
          <ChevronLeft aria-hidden="true" />
        </Link>
        <div className={styles.dateScroller}>
          {Array.from({ length: 7 }, (_, index) => {
            const day = addDays(date, index);
            return (
              <Link key={day} href={dateHref(day)}
                className={`${styles.dateChip} ${day === date ? styles.dateChipSelected : ""}`}
                aria-current={day === date ? "date" : undefined}>
                <span className={styles.dateLabel}>{labelFor(day, today)}</span>
                <span className={styles.dateValue}>
                  {new Intl.DateTimeFormat("en", { month: "short", day: "numeric", timeZone: "UTC" })
                    .format(new Date(`${day}T00:00:00Z`))}
                </span>
              </Link>
            );
          })}
        </div>
        <Link className={styles.stripArrow} href={dateHref(addDays(date, 1))} aria-label="Next day">
          <ChevronRight aria-hidden="true" />
        </Link>
      </nav>
      <nav className={styles.chipScroller} aria-label="Filter by league">
        {allLeagues.map((league) => {
          const count = league.code === "all" ? matches.length : leagueCounts.get(league.code) || 0;
          const query = new URLSearchParams({ date });
          if (league.code !== "all") query.set("league", league.code);
          return (
            <Link key={league.code} href={`/?${query.toString()}`}
              className={`${styles.leagueChip} ${selectedLeague === league.code ? styles.leagueChipSelected : ""}`}
              aria-current={selectedLeague === league.code ? "true" : undefined}>
              {league.emblem_url && <img className={styles.leagueEmblem} src={league.emblem_url} alt="" />}
              <span>{league.name}</span>
              <span className={styles.chipCount}>{count}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
