"use client";

import { useState } from "react";
import styles from "./ui.module.css";

function initials(name: string) {
  const words = name.replaceAll("&", " ").split(/\s+/).filter(Boolean)
    .filter((word) => !["fc", "afc", "cf", "sc"].includes(word.toLocaleLowerCase()));
  return words.length > 1
    ? `${words[0][0]}${words[1][0]}`.toUpperCase()
    : (words[0] || name).slice(0, 2).toUpperCase();
}

export default function TeamBadge({ name, crest, large = false }: { name: string; crest: string | null; large?: boolean }) {
  const [failed, setFailed] = useState(false);
  return (
    <span className={`${styles.badge} ${large ? styles.detailBadge : ""}`} aria-hidden="true">
      {crest && !failed
        ? <img src={crest} alt="" loading="lazy" decoding="async" onError={() => setFailed(true)} />
        : initials(name)}
    </span>
  );
}
