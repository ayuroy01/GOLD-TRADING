/**
 * Operator-visible readiness badges (Phase 3).
 *
 * Surfaces at a glance:
 *   - DATA: simulated vs real, freshness if available
 *   - LIVE: blocked vs ready, with hard-blocker count
 *   - ENV: practice vs live broker environment (only when live is enabled)
 *   - CUTOVER: whether LIVE_CUTOVER_ACKNOWLEDGED gate has been flipped
 *
 * The component does NOT make live trading look any closer to ready than it
 * actually is. If the broker is pointed at a real-money live account and the
 * cutover gate has not been acknowledged, a red CUTOVER badge appears.
 */

const COLORS = {
  good: "var(--green)",
  warn: "var(--amber)",
  bad: "var(--red)",
  muted: "var(--text-muted)",
};

function chip({ label, value, color, title }) {
  return (
    <span
      className="badge"
      title={title}
      style={{
        background: "rgba(255,255,255,0.05)",
        color,
        border: `1px solid ${color}`,
        fontSize: 10,
        fontWeight: 700,
        marginLeft: 6,
      }}
    >
      {label}: {value}
    </span>
  );
}

export default function ReadinessBadges({ health }) {
  if (!health) return null;

  // DATA badge ─────────────────────────────────────────
  const dataIsReal = health.data_is_real === true;
  const dataReady = health.data_provider_ready !== false;
  const dataLabel = dataIsReal ? "REAL" : "SIM";
  const dataColor = dataIsReal && dataReady ? COLORS.good : COLORS.muted;
  const age = health.data_last_quote_age_seconds;
  const dataValue =
    age != null ? `${dataLabel} · ${Math.round(age)}s` : dataLabel;
  const dataTitle = `Active provider: ${health.data_source ?? "unknown"} · ${
    dataReady ? "ready" : "NOT ready"
  }${age != null ? ` · last quote ${Math.round(age)}s ago` : ""}`;

  // LIVE badge ─────────────────────────────────────────
  const liveReady = health.live_ready === true;
  const liveLabel = liveReady ? "READY" : "BLOCKED";
  const liveColor = liveReady ? COLORS.good : COLORS.bad;
  const blockerRules = health.live_blocker_rules || [];
  const liveTitle = liveReady
    ? "Live execution gate is OPEN"
    : `Live execution BLOCKED (${health.live_blocker_count ?? blockerRules.length} hard blockers): ${
        blockerRules.join(", ") || "see /api/readiness"
      }`;

  // ENV + CUTOVER badges (only meaningful when live is enabled) ──────────
  const liveEnabled = health.live_enabled === true;
  const brokerEnv = health.live_broker_environment;
  const practiceMode = health.practice_mode === true;
  const cutoverAck = health.cutover_acknowledged === true;
  const cutoverBlocked = blockerRules.includes("cutover_not_acknowledged");

  const envBadge =
    liveEnabled && brokerEnv && brokerEnv !== "unknown"
      ? chip({
          label: "ENV",
          value: brokerEnv.toUpperCase(),
          color: practiceMode ? COLORS.good : COLORS.warn,
          title: practiceMode
            ? "Broker pointed at practice account — safe for dry-run."
            : "Broker pointed at REAL-MONEY live account.",
        })
      : null;

  const cutoverBadge =
    liveEnabled && brokerEnv === "live"
      ? chip({
          label: "CUTOVER",
          value: cutoverAck ? "ACK" : "NOT ACK",
          color: cutoverAck ? COLORS.good : COLORS.bad,
          title: cutoverAck
            ? "LIVE_CUTOVER_ACKNOWLEDGED=true — operator has asserted supervised practice validation is complete."
            : "LIVE_CUTOVER_ACKNOWLEDGED is not 'true'. Live orders are blocked until the supervised practice-account run is complete and the env var is set.",
        })
      : null;

  return (
    <>
      {chip({
        label: "DATA",
        value: dataValue,
        color: dataColor,
        title: dataTitle,
      })}
      {chip({
        label: "LIVE",
        value: liveLabel,
        color: liveColor,
        title: liveTitle,
      })}
      {envBadge}
      {cutoverBadge}
    </>
  );
}
