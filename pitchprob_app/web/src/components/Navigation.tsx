"use client";

import Link from "next/link";
import { BarChart3, CalendarDays, ClipboardList, type LucideIcon } from "lucide-react";
import { usePathname } from "next/navigation";
import styles from "@/app/layout.module.css";

const items: Array<{ href: string; label: string; Icon: LucideIcon }> = [
  { href: "/", label: "Matches", Icon: CalendarDays },
  { href: "/results", label: "Results", Icon: ClipboardList },
  { href: "/insights", label: "Insights", Icon: BarChart3 },
];

export default function Navigation({ mobile = false, collapsed = false }: { mobile?: boolean; collapsed?: boolean }) {
  const pathname = usePathname();
  const className = mobile ? styles.mobileNav : styles.nav;
  return (
    <nav className={className} aria-label={mobile ? "Main navigation" : "Primary"}>
      {items.map(({ href, label, Icon }) => {
        const active = href === "/" ? pathname === "/" || pathname.startsWith("/match/") : pathname.startsWith(href);
        return (
          <Link
            key={href}
            className={`${mobile ? styles.mobileLink : styles.navLink} ${active ? (mobile ? styles.mobileLinkActive : styles.navLinkActive) : ""}`}
            href={href}
            aria-current={active ? "page" : undefined}
            aria-label={collapsed && !mobile ? label : undefined}
            title={collapsed && !mobile ? label : undefined}
          >
            <Icon aria-hidden="true" />
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
