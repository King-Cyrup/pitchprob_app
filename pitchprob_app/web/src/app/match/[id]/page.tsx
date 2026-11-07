import AppHeader from "@/components/AppHeader";
import MatchDetailsTabs from "@/components/MatchDetailsTabs";
import { getMatch } from "@/lib/api";
import { notFound } from "next/navigation";
import styles from "@/components/ui.module.css";

export default async function MatchPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tab?: string }>;
}) {
  const [{ id }, query] = await Promise.all([params, searchParams]);
  if (!/^\d+$/.test(id) || Number(id) <= 0) {
    notFound();
  }
  const match = await getMatch(Number(id));
  const activeTab = query.tab || "overview";
  return (
    <div className={styles.pageGrid}>
      <AppHeader />
      <h1 className={styles.pageTitle}>Match details</h1>
      <MatchDetailsTabs match={match} activeTab={activeTab} />
      <footer className={styles.footer}>Times in UTC · Forecasts are statistical estimates, not betting advice. 18+ only.</footer>
    </div>
  );
}
