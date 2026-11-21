import AppHeader from "@/components/AppHeader";
import MatchesClient from "@/components/MatchesClient";
import { getDates, getMatch, getMatches } from "@/lib/api";
import styles from "@/components/ui.module.css";

type SearchParams = Promise<{ date?: string; league?: string; selected?: string; tab?: string }>;

function longDate(date: string) {
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "long", day: "numeric", month: "long", timeZone: "UTC",
  }).format(new Date(`${date}T00:00:00Z`));
}

export default async function MatchesPage({ searchParams }: { searchParams: SearchParams }) {
  const query = await searchParams;
  const today = new Date().toISOString().slice(0, 10);

  // Which days in the next fortnight actually have fixtures.
  const availability = await getDates(today, 14);
  const datesWithMatches = availability.filter((entry) => entry.total > 0);
  const todayHasMatches = datesWithMatches.some((entry) => entry.date === today);

  // Open on today when it has matches, otherwise on the next day that has some.
  const nextMatch = datesWithMatches.find((entry) => entry.date > today) ?? null;
  const date = query.date ?? (todayHasMatches ? today : nextMatch?.date ?? today);

  const data = await getMatches(date);
  const selectedId = query.selected && /^\d+$/.test(query.selected) && Number(query.selected) > 0
    ? Number(query.selected)
    : null;
  const selectedMatch = selectedId
    ? data.matches.find((match) => match.id === selectedId) ?? null
    : null;
  const selectedLeague = data.leagues.some((league) => league.code === query.league) ? query.league! : "all";
  const activeTab = query.tab || "overview";

  // The selected fixture needs its full details, not the summary row.
  let initialDetails = null;
  if (selectedId) {
    try {
      initialDetails = await getMatch(selectedId);
    } catch {
      initialDetails = null;
    }
  }

  return (
    <div className={styles.pageGrid}>
      <AppHeader />
      <MatchesClient
        date={date}
        today={today}
        matches={data.matches}
        leagues={data.leagues}
        selectedLeague={selectedLeague}
        initialSelectedMatch={selectedMatch}
        initialDetails={initialDetails}
        nextMatchDate={nextMatch?.date ?? null}
        nextMatchLabel={nextMatch ? longDate(nextMatch.date) : null}
        datesWithMatches={datesWithMatches.map((entry) => entry.date)}
        activeTab={activeTab}
      />
    </div>
  );
}
