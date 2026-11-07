import AppHeader from "@/components/AppHeader";
import MatchesClient from "@/components/MatchesClient";
import { getMatch, getMatches } from "@/lib/api";
import styles from "@/components/ui.module.css";

type SearchParams = Promise<{ date?: string; league?: string; selected?: string }>;

export default async function MatchesPage({ searchParams }: { searchParams: SearchParams }) {
  const query = await searchParams;
  const today = new Date().toISOString().slice(0, 10);
  const date = query.date || today;
  const data = await getMatches(date);
  const selectedId = query.selected && /^\d+$/.test(query.selected) && Number(query.selected) > 0
    ? Number(query.selected)
    : null;
  const selectedMatch = selectedId
    ? data.matches.find((match) => match.id === selectedId) ?? await getMatch(selectedId)
    : null;
  const selectedLeague = data.leagues.some((league) => league.code === query.league) ? query.league! : "all";

  return (
    <div className={styles.pageGrid}>
      <AppHeader />
      <MatchesClient date={date} today={today} matches={data.matches} leagues={data.leagues}
        selectedLeague={selectedLeague} initialSelectedMatch={selectedMatch} />
    </div>
  );
}
