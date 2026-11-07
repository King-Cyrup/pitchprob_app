import styles from "@/components/ui.module.css";

export default function Loading() {
  return (
    <div className={styles.pageGrid} aria-busy="true" aria-label="Loading matches">
      <div className={styles.skeletonHeader} />
      <p className={styles.muted} role="status">
        Loading matches… If this takes more than 10 seconds, check that the PitchProb data service is running.
      </p>
      <div className={styles.skeletonDate} />
      <div className={styles.skeletonRows}>
        {[0, 1, 2, 3, 4].map((row) => <div className={styles.skeletonRow} key={row} />)}
      </div>
    </div>
  );
}
