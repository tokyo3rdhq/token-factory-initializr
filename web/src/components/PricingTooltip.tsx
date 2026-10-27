/**
 * PricingTooltip - Tooltip/popover for detailed pricing information.
 *
 * Displays structured pricing details on hover/focus of the trigger element.
 * Follows the design system conventions and accessibility requirements.
 */

import { useState, useRef, useEffect, useCallback } from "react";
import type { ModelEndpoint } from "../types";
import { normalizePricingEntries, getPricingSource } from "../lib/pricing";

interface PricingTooltipProps {
  endpoint: ModelEndpoint;
  children: React.ReactElement;
  openDelay?: number;
  closeDelay?: number;
}

export function PricingTooltip({
  endpoint,
  children,
  openDelay = 200,
  closeDelay = 100,
}: PricingTooltipProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [position, setPosition] = useState<{ top: number; left: number }>({ top: 0, left: 0 });
  const tooltipRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLSpanElement>(null);
  const openTimeoutRef = useRef<number>();
  const closeTimeoutRef = useRef<number>();
  const pricingEntries = normalizePricingEntries(endpoint.pricing, getPricingSource(endpoint));
  const hasDetails = pricingEntries.length > 0;
  // const source = endpoint.data_source === "huggingface" ? endpoint.provider : endpoint.data_source;
  // const statusLabel = endpoint.pricing_status === "free"
  //   ? "Free"
  //   : endpoint.pricing_status === "priced"
  //   ? "Pricing"
  //   : "Unknown";
  const open = useCallback(() => {
    if (closeTimeoutRef.current) {
      window.clearTimeout(closeTimeoutRef.current);
    }
    openTimeoutRef.current = window.setTimeout(() => {
      setIsOpen(true);
    }, openDelay);
  }, [openDelay]);

  const close = useCallback(() => {
    if (openTimeoutRef.current) {
      window.clearTimeout(openTimeoutRef.current);
    }
    closeTimeoutRef.current = window.setTimeout(() => {
      setIsOpen(false);
    }, closeDelay);
  }, [closeDelay]);

  // Update position when trigger or tooltip changes
  useEffect(() => {
    if (!isOpen || !triggerRef.current || !tooltipRef.current) return;

    const triggerRect = triggerRef.current.getBoundingClientRect();
    const tooltipRect = tooltipRef.current.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    // const viewportHeight = window.innerHeight;

    // Position above the trigger by default
    let top = triggerRect.top - tooltipRect.height - 8;
    let left = triggerRect.left + triggerRect.width / 2 - tooltipRect.width / 2;

    // Adjust if would go off top
    if (top < 8) {
      top = triggerRect.bottom + 8;
    }

    // Adjust horizontal bounds
    if (left < 8) left = 8;
    if (left + tooltipRect.width > viewportWidth - 8) {
      left = viewportWidth - tooltipRect.width - 8;
    }

    setPosition({ top, left });
  }, [isOpen]);
  // Handle escape key
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIsOpen(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  if (!isOpen) {
    return (
      <span
        ref={triggerRef}
        onMouseEnter={open}
        onMouseLeave={close}
        onFocus={open}
        onBlur={close}
      >
        {children}
      </span>
    );
  }

  return (
    <>
      <span
        ref={triggerRef}
        onMouseEnter={open}
        onMouseLeave={close}
        onFocus={open}
        onBlur={close}
      >
        {children}
      </span>
      <div
        ref={tooltipRef}
        className="tfi-pricing-tooltip"
        style={{
          position: "fixed",
          top: position.top,
          left: position.left,
          zIndex: 1000,
          pointerEvents: "auto",
        }}
        role="tooltip"
        aria-label="Pricing details"
      >
        <div className="tfi-pricing-tooltip-content">
          <div className="tfi-pricing-tooltip-body">
            {(() => {
              const entries = normalizePricingEntries(
                endpoint.pricing,
                endpoint.data_source === "huggingface" ? endpoint.provider : endpoint.data_source,
              );
              const hasDetails = entries.length > 0;

              if (!hasDetails) {
                return (
                  <p className="tfi-pricing-tooltip-empty">
                    {endpoint.pricing_status === "unknown"
                      ? "Pricing information unavailable"
                      : "No detailed pricing available"}
                  </p>
                );
              }

              return (
                <table className="tfi-pricing-tooltip-table">
                  <tbody>
                    {entries.map((entry) => (
                      <tr key={entry.key} className="tfi-pricing-tooltip-row">
                        <td className="tfi-pricing-tooltip-label">{entry.label}</td>
                        <td className="tfi-pricing-tooltip-value">{entry.formatted}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              );
            })()}
          </div>

          {endpoint.pricing_status === "free" && hasDetails && (
            <p className="tfi-pricing-tooltip-note">
              Zero prices are confirmed free. Unlisted operations may not be free.
            </p>
          )}

        </div>
      </div>
    </>
  );
}

export default PricingTooltip;