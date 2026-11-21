"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { Match, MatchDetails } from "@/lib/types";
import DateStrip from "@/components/DateStrip";
import MatchDetailsTabs from "@/components/MatchDetailsTabs";
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
  initialDetails,
  nextMatchDate,
  nextMatchLabel,
  datesWithMatches,
  activeTab,
}: {
  date: string;
  today: string;
  matches: Match[];
  leagues: League[];
  selectedLeague: string;
  initialSelectedMatch: Match | null;
  initialDetails: MatchDetails | null;
  nextMatchDate: string | null;
  nextMatchLabel: string | null;
  datesWithMatches: string[];
  activeTab: string;
}) {
  const router = useRouter();
  const [selectedId, setSelectedId] = useState<number | null>(initialSelectedMatch?.id ?? null);
  const [details, setDetails] = useState<MatchDetails | null>(initialDetails);
  const [detailsError, setDetailsError] = useState(false);
  const [loadingDetails, setLoadingDetails] = useState(false);

  // Keep the pane in sync when the URL changes (server re-render with ?selected=).
  useEffect(() => {
    setSelectedId(initialSelectedMatch?.id ?? null);
    setDetails(initialDetails);
    setDetailsError(false);
  }, [initialSelectedMatch, initialDetails]);

  // Fetch full details when the user picks a fixture before the server round-trip finishes.
  useEffect(() => {
    if (selectedId === null) {
      setDetails(null);
      setDetailsError(false);
      return;
    }
    if (initialDetails && initialDetails.id === selectedId) {
      setDetails(initialDetails);
      setDetailsError(false);
      return;
    }
    let cancelled = false;
    setLoadingDetails(true);
    setDetailsError(false);
    fetch(`/api/matches/${selectedId}`)
      .then(async (response) => {
        if (!response.ok) throw new Error(String(response.status));
        return response.json() as Promise<MatchDetails>;
      })
      .then((payload) => {
        if (!cancelled) setDetails(payload);
      })
      .catch(() => {
        if (!cancelled) {
          setDetails(null);
          setDetailsError(true);
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingDetails(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId, initialDetails]);

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

  function selectMatch(match: Match) {
    setSelectedId(match.id);
  }

  return (
    <>
      <div className={styles.pageTitleRow}>
        <h1 className={styles.pageTitle}>Matches</h1>
        <span className={styles.subtleTitle}>Times in UTC</span>
      </div>
      <DateStrip date={date} matches={matches} leagues={leagues} selectedLeague={selectedLeague} today={today}
        datesWithMatches={datesWithMatches} />
      <div className={styles.matchLayout}>
        <section className={styles.matchListPane} aria-label="Match list">
          <div className={styles.listHeading}>
            <h2>Fixtures</h2>
            <span>{staleMessage || `${visibleMatches.length} ${visibleMatches.length === 1 ? "match" : "matches"}`}</span>
          </div>
          {groups.length ? groups.map((group) => (
            <MatchGroup key={group.code} code={group.code} name={group.name}
              emblemUrl={group.emblem_url} matches={group.matches} date={date}
              selectedId={selectedId}
              onSelect={selectMatch} />
          )) : (
            <div className={styles.empty}>
              <strong>No matches on this day.</strong>
              {nextMatchDate ? (
                <>
                  <span>The next fixtures are on {nextMatchLabel}.</span>
                  <Link className={styles.textLink} href={`/?date=${nextMatchDate}`}>Go to {nextMatchLabel}</Link>
                </>
              ) : (
                <span>There are no fixtures in the next 14 days.</span>
              )}
            </div>
          )}
        </section>
        <aside className={styles.detailPane} aria-label="Selected match">
          {detailsError ? (
            <div className={styles.errorBox} role="alert">
              <p className={styles.sectionTitle}>Could not load this match</p>
              <p className={styles.muted}>The match details service did not answer. Try again.</p>
              <button className={styles.retryButton} type="button" onClick={() => {
                setDetailsError(false);
                setSelectedId(null);
                router.refresh();
              }}>Retry</button>
            </div>
          ) : loadingDetails && !details ? (
            <div className={styles.detailPlaceholder} aria-busy="true">
              <div className={styles.skeletonHeader} />
              <div className={styles.skeletonDate} />
              <div className={styles.skeletonRow} />
            </div>
          ) : details ? (
            <MatchDetailsTabs match={details} activeTab={activeTab} showBackLink={false}
              linkBase={`/?date=${date}&selected=${details.id}`} />
          ) : (
            <div className={styles.detailPlaceholder}>
              <p className={styles.placeholderTitle}>Match details</p>
              <p className={styles.muted}>Select a fixture to see its match details here.</p>
              {nextMatchLabel && <p className={styles.muted}>Next kickoff: {nextMatchLabel}.</p>}
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
