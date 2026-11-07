import Link from "next/link";
import styles from "@/components/ui.module.css";

export default function NotFound() {
  return (
    <div className={styles.empty}>
      <h1 className={styles.sectionTitle}>Match not found</h1>
      <p>The match may no longer be available.</p>
      <Link className={styles.textLink} href="/">Back to matches</Link>
    </div>
  );
}
