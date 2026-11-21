import { CheckCircle2, FlaskConical, HelpCircle } from "lucide-react";
import type { MarketValidation, ValidationStatus } from "@/lib/types";
import styles from "./ui.module.css";

const labels: Record<ValidationStatus, string> = {
  validated: "Tested",
  experimental: "Not yet proven",
  unavailable: "Not tested",
};

/**
 * A small badge that says how well the model has been tested on this market.
 * The tooltip carries the numbers; the icon and the word carry the meaning, so
 * the badge never relies on colour alone.
 */
export default function ValidationBadge({
  validation,
  market,
}: {
  validation: MarketValidation | null | undefined;
  market: string;
}) {
  const status: ValidationStatus = validation?.status ?? "unavailable";
  const Icon = status === "validated" ? CheckCircle2 : status === "experimental" ? FlaskConical : HelpCircle;
  const detail = validation && validation.model_loss !== null && validation.baseline_loss !== null
    ? `Tested on ${validation.n} past matches: model ${validation.model_loss.toFixed(3)} against `
      + `${validation.baseline_loss.toFixed(3)} for no model (lower is better).`
    : `This market has not been tested on past matches yet.`;

  return (
    <span
      className={`${styles.validationBadge} ${styles[`validation${status[0].toUpperCase()}${status.slice(1)}`]}`}
      title={detail}
      tabIndex={0}
      aria-label={`${labels[status]}: ${detail}`}
    >
      <Icon aria-hidden="true" />
      {labels[status]}
    </span>
  );
}
