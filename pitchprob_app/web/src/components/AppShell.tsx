"use client";

import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useState, type ReactNode } from "react";
import Navigation from "@/components/Navigation";
import styles from "@/app/layout.module.css";

export default function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className={`${styles.frame} ${collapsed ? styles.frameCollapsed : ""}`}>
      <aside className={`${styles.rail} ${collapsed ? styles.railCollapsed : ""}`}>
        <div className={styles.railHeader}>
          <a className={styles.railBrand} href="/" aria-label="PitchProb home">
            <span className={styles.brandFull}>PitchProb</span>
            <span className={styles.brandCompact}>P</span>
          </a>
          <button
            className={styles.railToggle}
            type="button"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!collapsed}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            onClick={() => setCollapsed((current) => !current)}
          >
            {collapsed ? <PanelLeftOpen aria-hidden="true" /> : <PanelLeftClose aria-hidden="true" />}
          </button>
        </div>
        <Navigation collapsed={collapsed} />
        <p className={styles.railNote}>Statistical estimates.</p>
      </aside>
      <main className={styles.content}>{children}</main>
      <Navigation mobile />
    </div>
  );
}
