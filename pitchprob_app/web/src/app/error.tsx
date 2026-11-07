"use client";

import { RefreshCw } from "lucide-react";
import styles from "@/components/ui.module.css";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className={styles.errorBox} role="alert">
      <h1 className={styles.sectionTitle}>We couldn’t load this page</h1>
      <p className={styles.muted}>
        The match data service could not be reached. Make sure the FastAPI service is running and{" "}
        <code>API_BASE_URL</code> points to it. For the default setup, start it from the pitchprob_app
        folder with <code>uvicorn app:app --port 8080</code>, then try again.
      </p>
      <button className={styles.retryButton} type="button" onClick={reset}><RefreshCw aria-hidden="true" /> Try again</button>
    </div>
  );
}
