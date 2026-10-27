/**
 * PricingBadge - Status badge for model pricing.
 *
 * Renders the appropriate badge based on the endpoint's pricing_status.
 * Uses magi-design-system Badge with correct variants and dot prop.
 */

import { forwardRef } from "react";
import { Badge } from "@tokyo3rdhq/magi-design-system";
import type { ModelEndpoint } from "../types";
import { getPricingStatusLabel, getPricingStatusVariant, getPricingStatusDot } from "../lib/pricing";

interface PricingBadgeProps {
  endpoint: ModelEndpoint;
  /** Additional CSS classes */
  className?: string;
}

export const PricingBadge = forwardRef<HTMLSpanElement, PricingBadgeProps>(
  ({ endpoint, className }, ref) => {
    const status = endpoint.pricing_status ?? "unknown";
    const label = getPricingStatusLabel(status);
    const variant = getPricingStatusVariant(status);
    const dot = getPricingStatusDot(status);

    return (
      <Badge ref={ref} variant={variant} dot={dot} className={`tfi-pricing-badge ${className ?? ""}`}>
        {label}
      </Badge>
    );
  }
);

PricingBadge.displayName = "PricingBadge";

export default PricingBadge;