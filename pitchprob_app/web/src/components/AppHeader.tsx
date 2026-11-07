import ThemeToggle from "@/components/ThemeToggle";
import styles from "./ui.module.css";

export default function AppHeader() {
  return (
    <header className={styles.pageHeader}>
      <div>
        <p className={styles.brand}>PitchProb</p>
        <p className={styles.description}>Statistical forecasts. A clear record.</p>
      </div>
      <div className={styles.headerActions}>
        <span className={styles.utc}>Times in UTC</span>
        <ThemeToggle />
      </div>
    </header>
  );
}
