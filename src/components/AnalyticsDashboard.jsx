import { useMemo } from "react";
import { computeAllAnalytics, equityCurve, drawdown, tradeDistribution } from "../engine/mathEngine.js";
import { loadTrades, getClosedTrades, getRMultiples } from "../data/tradeStore.js";

// ─── Color palette ──────────────────────────────────────────────────────────
const C = {
  bg: "#0a0e17",
  card: "#111827",
  border: "#1e293b",
  textPrimary: "#e2e8f0",
  textMuted: "#64748b",
  green: "#10b981",
  red: "#ef4444",
  accent: "#3b82f6",
  chartBg: "#0f172a",
  yellow: "#f59e0b",
  mono: "'SF Mono', 'Fira Code', monospace",
  sans: "system-ui, -apple-system, sans-serif",
};

// ─── Helpers ─────────────────────────────────────────────────────────────────
function fmt(n, decimals = 2) {
  if (n == null || isNaN(n)) return "—";
  return n.toFixed(decimals);
}

function fmtPct(n, decimals = 1) {
  if (n == null || isNaN(n)) return "—";
  return (n * 100).toFixed(decimals) + "%";
}

// ─── Shared card style ────────────────────────────────────────────────────────
function cardStyle(extra = {}) {
  return {
    background: C.card,
    border: `1px solid ${C.border}`,
    borderRadius: 8,
    padding: "16px 20px",
    fontFamily: C.sans,
    ...extra,
  };
}

// ─── MetricCard ───────────────────────────────────────────────────────────────
function MetricCard({ label, value, sub, warn, accent }) {
  const valueColor = warn ? C.red : accent ? C.accent : C.textPrimary;
  return (
    <div style={cardStyle({ display: "flex", flexDirection: "column", gap: 6, minWidth: 130 })}>
      <span style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: C.textMuted, fontFamily: C.sans }}>
        {label}
      </span>
      <span style={{ fontSize: 22, fontWeight: 700, fontFamily: C.mono, color: valueColor, lineHeight: 1.1 }}>
        {value}
      </span>
      {sub && (
        <span style={{ fontSize: 11, color: C.textMuted, fontFamily: C.sans, marginTop: 2 }}>
          {sub}
        </span>
      )}
    </div>
  );
}

// ─── Phase Indicator ─────────────────────────────────────────────────────────
function PhaseIndicator({ analytics }) {
  const { phase, totalTrades, edgeStatus } = analytics;

  const phaseTargets = [50, 150, 300];
  const phaseMins = [0, 50, 150];
  const phaseLabels = ["Phase 1", "Phase 2", "Phase 3"];
  const phaseDescs = ["Foundation: Execution mastery", "Validation: Edge confirmation", "Scaling: System deployment"];

  const phaseIdx = phase - 1;
  const min = phaseMins[phaseIdx];
  const max = phaseTargets[phaseIdx];
  const progress = Math.min(1, (totalTrades - min) / (max - min));

  const edgeColor =
    edgeStatus.includes("VALIDATED") ? C.green :
    edgeStatus.includes("NOT CONFIRMED") ? C.red :
    edgeStatus.includes("Warning") ? C.yellow :
    C.accent;

  return (
    <div style={cardStyle({ display: "flex", flexDirection: "column", gap: 12 })}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <span style={{ fontSize: 13, fontWeight: 700, color: C.accent, fontFamily: C.sans, marginRight: 8 }}>
            {phaseLabels[phaseIdx]}
          </span>
          <span style={{ fontSize: 12, color: C.textMuted, fontFamily: C.sans }}>
            {phaseDescs[phaseIdx]}
          </span>
        </div>
        <span style={{
          fontSize: 11,
          fontFamily: C.mono,
          color: edgeColor,
          background: edgeColor + "22",
          border: `1px solid ${edgeColor}44`,
          borderRadius: 4,
          padding: "3px 8px",
          whiteSpace: "nowrap",
        }}>
          {edgeStatus}
        </span>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ flex: 1, height: 6, background: C.chartBg, borderRadius: 3, overflow: "hidden" }}>
          <div style={{
            height: "100%",
            width: `${progress * 100}%`,
            background: progress >= 1 ? C.green : C.accent,
            borderRadius: 3,
            transition: "width 0.4s ease",
          }} />
        </div>
        <span style={{ fontSize: 12, fontFamily: C.mono, color: C.textMuted, whiteSpace: "nowrap" }}>
          {totalTrades} / {max} trades
        </span>
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        {[1, 2, 3].map(p => (
          <div key={p} style={{
            flex: 1,
            height: 4,
            borderRadius: 2,
            background: p < phase ? C.green : p === phase ? C.accent : C.border,
            opacity: p > phase ? 0.4 : 1,
          }} />
        ))}
      </div>
    </div>
  );
}

// ─── Equity Curve SVG ────────────────────────────────────────────────────────
function EquityCurveChart({ curve }) {
  if (!curve || curve.length < 2) return null;

  const W = 800;
  const H = 220;
  const PAD = { top: 16, right: 24, bottom: 36, left: 52 };
  const iW = W - PAD.left - PAD.right;
  const iH = H - PAD.top - PAD.bottom;

  const minVal = Math.min(...curve);
  const maxVal = Math.max(...curve);
  const range = maxVal - minVal || 1;
  const paddedMin = minVal - range * 0.1;
  const paddedMax = maxVal + range * 0.1;
  const paddedRange = paddedMax - paddedMin;

  const xScale = (i) => PAD.left + (i / (curve.length - 1)) * iW;
  const yScale = (v) => PAD.top + iH - ((v - paddedMin) / paddedRange) * iH;
  const zeroY = yScale(0);

  const points = curve.map((v, i) => [xScale(i), yScale(v)]);
  const polyline = points.map(([x, y]) => `${x},${y}`).join(" ");

  // Area path
  const areaPath = [
    `M ${points[0][0]},${zeroY}`,
    ...points.map(([x, y]) => `L ${x},${y}`),
    `L ${points[points.length - 1][0]},${zeroY}`,
    "Z",
  ].join(" ");

  // Determine line color by final value
  const finalVal = curve[curve.length - 1];
  const lineColor = finalVal >= 0 ? C.green : C.red;
  const areaColor = finalVal >= 0 ? C.green : C.red;

  // Y axis ticks
  const yTicks = 5;
  const yTickValues = Array.from({ length: yTicks + 1 }, (_, i) =>
    paddedMin + (paddedRange / yTicks) * i
  );

  // X axis ticks (max 8)
  const xTickCount = Math.min(8, curve.length - 1);
  const xTickIndices = Array.from({ length: xTickCount + 1 }, (_, i) =>
    Math.round((i / xTickCount) * (curve.length - 1))
  );

  return (
    <div style={cardStyle({ padding: "16px 20px 8px" })}>
      <div style={{ fontSize: 12, color: C.textMuted, fontFamily: C.sans, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.07em" }}>
        Equity Curve (Cumulative R)
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: "block", background: C.chartBg, borderRadius: 6 }}>
        <defs>
          <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={areaColor} stopOpacity="0.22" />
            <stop offset="100%" stopColor={areaColor} stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* Grid lines */}
        {yTickValues.map((v, i) => (
          <line
            key={i}
            x1={PAD.left}
            y1={yScale(v)}
            x2={W - PAD.right}
            y2={yScale(v)}
            stroke={C.border}
            strokeWidth={0.5}
          />
        ))}

        {/* Zero line */}
        {paddedMin <= 0 && paddedMax >= 0 && (
          <line
            x1={PAD.left}
            y1={zeroY}
            x2={W - PAD.right}
            y2={zeroY}
            stroke={C.textMuted}
            strokeWidth={1}
            strokeDasharray="4,4"
          />
        )}

        {/* Area fill */}
        <path d={areaPath} fill="url(#areaGrad)" />

        {/* Line */}
        <polyline
          points={polyline}
          fill="none"
          stroke={lineColor}
          strokeWidth={1.8}
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {/* Dots — only show if not too many points */}
        {curve.length <= 60 && points.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r={2.5} fill={lineColor} opacity={0.8} />
        ))}

        {/* Y axis labels */}
        {yTickValues.map((v, i) => (
          <text
            key={i}
            x={PAD.left - 6}
            y={yScale(v) + 4}
            textAnchor="end"
            fontSize={9}
            fill={C.textMuted}
            fontFamily={C.mono}
          >
            {v.toFixed(1)}R
          </text>
        ))}

        {/* X axis labels */}
        {xTickIndices.map((idx, i) => (
          <text
            key={i}
            x={xScale(idx)}
            y={H - PAD.bottom + 16}
            textAnchor="middle"
            fontSize={9}
            fill={C.textMuted}
            fontFamily={C.mono}
          >
            {idx}
          </text>
        ))}

        {/* Axis label */}
        <text
          x={PAD.left + iW / 2}
          y={H - 4}
          textAnchor="middle"
          fontSize={9}
          fill={C.textMuted}
          fontFamily={C.sans}
        >
          Trade #
        </text>
        <text
          x={10}
          y={PAD.top + iH / 2}
          textAnchor="middle"
          fontSize={9}
          fill={C.textMuted}
          fontFamily={C.sans}
          transform={`rotate(-90, 10, ${PAD.top + iH / 2})`}
        >
          Cum. R
        </text>
      </svg>
    </div>
  );
}

// ─── Drawdown Chart SVG ───────────────────────────────────────────────────────
function DrawdownChart({ series }) {
  if (!series || series.length < 2) return null;

  const W = 800;
  const H = 160;
  const PAD = { top: 16, right: 24, bottom: 36, left: 52 };
  const iW = W - PAD.left - PAD.right;
  const iH = H - PAD.top - PAD.bottom;

  const maxDD = Math.max(...series, 0.01);

  const xScale = (i) => PAD.left + (i / (series.length - 1)) * iW;
  // drawdown is always >= 0, we render it going downward from top
  const yScale = (v) => PAD.top + (v / maxDD) * iH;

  const points = series.map((v, i) => [xScale(i), yScale(v)]);

  const areaPath = [
    `M ${points[0][0]},${PAD.top}`,
    ...points.map(([x, y]) => `L ${x},${y}`),
    `L ${points[points.length - 1][0]},${PAD.top}`,
    "Z",
  ].join(" ");

  const xTickCount = Math.min(8, series.length - 1);
  const xTickIndices = Array.from({ length: xTickCount + 1 }, (_, i) =>
    Math.round((i / xTickCount) * (series.length - 1))
  );

  const yTicks = 4;
  const yTickValues = Array.from({ length: yTicks + 1 }, (_, i) => (maxDD / yTicks) * i);

  return (
    <div style={cardStyle({ padding: "16px 20px 8px" })}>
      <div style={{ fontSize: 12, color: C.textMuted, fontFamily: C.sans, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.07em" }}>
        Drawdown from Peak (R)
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: "block", background: C.chartBg, borderRadius: 6 }}>
        <defs>
          <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={C.red} stopOpacity="0.35" />
            <stop offset="100%" stopColor={C.red} stopOpacity="0.05" />
          </linearGradient>
        </defs>

        {yTickValues.map((v, i) => (
          <line
            key={i}
            x1={PAD.left}
            y1={yScale(v)}
            x2={W - PAD.right}
            y2={yScale(v)}
            stroke={C.border}
            strokeWidth={0.5}
          />
        ))}

        <path d={areaPath} fill="url(#ddGrad)" />

        <polyline
          points={points.map(([x, y]) => `${x},${y}`).join(" ")}
          fill="none"
          stroke={C.red}
          strokeWidth={1.4}
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {yTickValues.map((v, i) => (
          <text
            key={i}
            x={PAD.left - 6}
            y={yScale(v) + 4}
            textAnchor="end"
            fontSize={9}
            fill={C.textMuted}
            fontFamily={C.mono}
          >
            {v.toFixed(1)}R
          </text>
        ))}

        {xTickIndices.map((idx, i) => (
          <text
            key={i}
            x={xScale(idx)}
            y={H - PAD.bottom + 16}
            textAnchor="middle"
            fontSize={9}
            fill={C.textMuted}
            fontFamily={C.mono}
          >
            {idx}
          </text>
        ))}

        <text
          x={PAD.left + iW / 2}
          y={H - 4}
          textAnchor="middle"
          fontSize={9}
          fill={C.textMuted}
          fontFamily={C.sans}
        >
          Trade #
        </text>
      </svg>
    </div>
  );
}

// ─── R-Multiple Distribution SVG ─────────────────────────────────────────────
function DistributionChart({ distribution }) {
  if (!distribution || distribution.length === 0) return null;

  const W = 800;
  const H = 180;
  const PAD = { top: 24, right: 24, bottom: 48, left: 40 };
  const iW = W - PAD.left - PAD.right;
  const iH = H - PAD.top - PAD.bottom;

  const maxCount = Math.max(...distribution.map(b => b.count), 1);
  const barWidth = (iW / distribution.length) * 0.72;
  const gap = (iW / distribution.length) * 0.28;

  const negBuckets = new Set(["< -2R", "-2R to -1R", "-1R to 0R"]);

  return (
    <div style={cardStyle({ padding: "16px 20px 8px" })}>
      <div style={{ fontSize: 12, color: C.textMuted, fontFamily: C.sans, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.07em" }}>
        R-Multiple Distribution
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: "block", background: C.chartBg, borderRadius: 6 }}>
        {/* Baseline */}
        <line
          x1={PAD.left}
          y1={PAD.top + iH}
          x2={W - PAD.right}
          y2={PAD.top + iH}
          stroke={C.border}
          strokeWidth={1}
        />

        {distribution.map((b, i) => {
          const barH = maxCount > 0 ? (b.count / maxCount) * iH : 0;
          const x = PAD.left + i * (iW / distribution.length) + gap / 2;
          const y = PAD.top + iH - barH;
          const isNeg = negBuckets.has(b.bucket);
          const barColor = isNeg ? C.red : C.green;

          return (
            <g key={i}>
              <rect
                x={x}
                y={y}
                width={barWidth}
                height={barH}
                fill={barColor}
                opacity={b.count > 0 ? 0.8 : 0.15}
                rx={2}
              />
              {/* Count label on bar */}
              {b.count > 0 && (
                <text
                  x={x + barWidth / 2}
                  y={y - 4}
                  textAnchor="middle"
                  fontSize={10}
                  fill={barColor}
                  fontFamily={C.mono}
                  fontWeight={700}
                >
                  {b.count}
                </text>
              )}
              {/* Bucket label */}
              <text
                x={x + barWidth / 2}
                y={PAD.top + iH + 14}
                textAnchor="middle"
                fontSize={8.5}
                fill={C.textMuted}
                fontFamily={C.mono}
              >
                {b.bucket}
              </text>
              {/* Pct label */}
              {b.count > 0 && (
                <text
                  x={x + barWidth / 2}
                  y={PAD.top + iH + 26}
                  textAnchor="middle"
                  fontSize={8}
                  fill={C.textMuted}
                  fontFamily={C.sans}
                >
                  {b.pct}%
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ─── Validation Checklist ─────────────────────────────────────────────────────
function ValidationChecklist({ analytics, closedTrades }) {
  const { phase, totalTrades, expectancy, evAtCiLow, maxDrawdownPct, profitFactor: pf } = analytics;

  const behavioralErrors = closedTrades.filter(
    t => t.error && t.error !== "None" && t.error === "Behavioral"
  ).length;
  const behavioralErrorPct = totalTrades > 0 ? behavioralErrors / totalTrades : 0;

  const avgLoss = closedTrades
    .filter(t => t.rMultiple != null && t.rMultiple < 0)
    .map(t => t.rMultiple);
  const avgLossR = avgLoss.length
    ? avgLoss.reduce((a, b) => a + b, 0) / avgLoss.length
    : null;

  const checks = phase === 1
    ? [
        {
          label: "50 qualifying trades logged",
          pass: totalTrades >= 50,
          detail: `${totalTrades} / 50`,
        },
        {
          label: "Avg loss between -0.8R and -1.2R",
          pass: avgLossR != null && avgLossR >= -1.2 && avgLossR <= -0.8,
          detail: avgLossR != null ? `${fmt(avgLossR)}R` : "No losses yet",
        },
        {
          label: "Zero behavioral errors",
          pass: behavioralErrors === 0,
          detail: `${behavioralErrors} behavioral error(s)`,
        },
      ]
    : phase === 2
    ? [
        {
          label: "Expectancy > 0R",
          pass: expectancy > 0,
          detail: `${fmt(expectancy)}R`,
        },
        {
          label: "EV at CI lower > -0.3R",
          pass: evAtCiLow > -0.3,
          detail: `${fmt(evAtCiLow)}R`,
        },
        {
          label: "Max drawdown < 8%",
          pass: maxDrawdownPct < 8,
          detail: `${fmt(maxDrawdownPct)}%`,
        },
        {
          label: "Behavioral errors < 10%",
          pass: behavioralErrorPct < 0.1,
          detail: `${(behavioralErrorPct * 100).toFixed(1)}%`,
        },
      ]
    : [
        {
          label: "Expectancy > +0.20R",
          pass: expectancy > 0.2,
          detail: `${fmt(expectancy)}R`,
        },
        {
          label: "EV at CI lower > 0R",
          pass: evAtCiLow > 0,
          detail: `${fmt(evAtCiLow)}R`,
        },
        {
          label: "Profit factor > 1.3",
          pass: pf > 1.3,
          detail: `${fmt(pf)}`,
        },
        {
          label: "2+ market regimes documented",
          pass: false,
          detail: "Manual verification required",
          manual: true,
        },
      ];

  const passed = checks.filter(c => c.pass).length;
  const allPass = passed === checks.length;

  return (
    <div style={cardStyle({ display: "flex", flexDirection: "column", gap: 12 })}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: 12, color: C.textMuted, fontFamily: C.sans, textTransform: "uppercase", letterSpacing: "0.07em" }}>
          Phase {phase} Validation Checklist
        </span>
        <span style={{
          fontSize: 11,
          fontFamily: C.mono,
          color: allPass ? C.green : C.textMuted,
          background: allPass ? C.green + "22" : C.chartBg,
          border: `1px solid ${allPass ? C.green + "44" : C.border}`,
          borderRadius: 4,
          padding: "2px 8px",
        }}>
          {passed} / {checks.length} passed
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {checks.map((c, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "8px 12px",
              background: C.chartBg,
              borderRadius: 6,
              border: `1px solid ${c.pass ? C.green + "33" : c.manual ? C.border : C.red + "33"}`,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{
                fontSize: 13,
                color: c.pass ? C.green : c.manual ? C.textMuted : C.red,
                fontWeight: 700,
                lineHeight: 1,
              }}>
                {c.pass ? "✓" : c.manual ? "?" : "✗"}
              </span>
              <span style={{ fontSize: 12, color: c.pass ? C.textPrimary : C.textMuted, fontFamily: C.sans }}>
                {c.label}
              </span>
            </div>
            <span style={{
              fontSize: 11,
              fontFamily: C.mono,
              color: c.pass ? C.green : c.manual ? C.textMuted : C.red,
            }}>
              {c.detail}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Empty State ──────────────────────────────────────────────────────────────
function EmptyState() {
  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: "80px 24px",
      gap: 16,
      color: C.textMuted,
      fontFamily: C.sans,
    }}>
      <div style={{ fontSize: 48, opacity: 0.3 }}>◈</div>
      <div style={{ fontSize: 18, fontWeight: 600, color: C.textPrimary }}>No closed trades yet</div>
      <div style={{ fontSize: 14, textAlign: "center", maxWidth: 380, lineHeight: 1.6 }}>
        Close your first trade to begin analytics tracking. The dashboard will populate with
        performance metrics, equity curve, and distribution analysis.
      </div>
    </div>
  );
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────
export default function AnalyticsDashboard({ trades }) {
  const closedTrades = useMemo(
    () => (trades || []).filter(t => t.status === "closed" && t.rMultiple != null),
    [trades]
  );

  const rMultiples = useMemo(
    () => closedTrades.map(t => t.rMultiple),
    [closedTrades]
  );

  const analytics = useMemo(
    () => computeAllAnalytics(rMultiples),
    [rMultiples]
  );

  const curve = useMemo(
    () => (rMultiples.length ? equityCurve(rMultiples) : []),
    [rMultiples]
  );

  const ddData = useMemo(
    () => (rMultiples.length ? drawdown(rMultiples) : null),
    [rMultiples]
  );

  const distribution = useMemo(
    () => (rMultiples.length ? tradeDistribution(rMultiples) : []),
    [rMultiples]
  );

  const containerStyle = {
    background: C.bg,
    minHeight: "100vh",
    padding: "24px",
    fontFamily: C.sans,
    color: C.textPrimary,
    boxSizing: "border-box",
  };

  if (!closedTrades.length) {
    return (
      <div style={containerStyle}>
        <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 24, color: C.textPrimary, fontFamily: C.sans }}>
          Analytics Dashboard
        </div>
        <div style={cardStyle()}>
          <EmptyState />
        </div>
      </div>
    );
  }

  const {
    totalTrades,
    wins,
    losses,
    winRate,
    ciLow,
    ciHigh,
    expectancy,
    evAtCiLow,
    profitFactor: pf,
    sharpe,
    maxLosingStreak: maxStreak,
    maxDrawdownR,
    riskOfRuin: ror,
    phase,
  } = analytics;

  const rorDisplay =
    ror == null
      ? "N/A"
      : ror >= 1
      ? "100%"
      : (ror * 100).toFixed(2) + "%";

  const isRorNA = rMultiples.length < 10;

  return (
    <div style={containerStyle}>
      {/* Header */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        marginBottom: 24,
        flexWrap: "wrap",
        gap: 12,
      }}>
        <div>
          <div style={{ fontSize: 20, fontWeight: 700, color: C.textPrimary }}>
            Analytics Dashboard
          </div>
          <div style={{ fontSize: 12, color: C.textMuted, marginTop: 3 }}>
            {totalTrades} closed trade{totalTrades !== 1 ? "s" : ""} analyzed
          </div>
        </div>
        <div style={{
          fontSize: 11,
          fontFamily: C.mono,
          color: C.textMuted,
          background: C.chartBg,
          border: `1px solid ${C.border}`,
          borderRadius: 4,
          padding: "4px 10px",
        }}>
          XAUUSD · GOLD V1 SYSTEM
        </div>
      </div>

      {/* Phase Indicator */}
      <div style={{ marginBottom: 16 }}>
        <PhaseIndicator analytics={analytics} />
      </div>

      {/* Metric Cards Grid */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(145px, 1fr))",
        gap: 12,
        marginBottom: 16,
      }}>
        <MetricCard
          label="Total Trades"
          value={totalTrades}
          sub={`${wins}W / ${losses}L`}
        />
        <MetricCard
          label="Win Rate"
          value={fmtPct(winRate)}
          sub={`95% CI: ${fmtPct(ciLow)} – ${fmtPct(ciHigh)}`}
        />
        <MetricCard
          label="Expectancy (R)"
          value={`${fmt(expectancy)}R`}
          warn={expectancy < 0}
          accent={expectancy > 0}
          sub={expectancy < 0 ? "Negative edge" : "Per trade"}
        />
        <MetricCard
          label="EV at CI Low"
          value={`${fmt(evAtCiLow)}R`}
          warn={evAtCiLow < 0}
          sub="Pessimistic estimate"
        />
        <MetricCard
          label="Profit Factor"
          value={isFinite(pf) ? fmt(pf) : "∞"}
          warn={pf < 1}
          accent={pf >= 1.3}
          sub={pf < 1 ? "Below breakeven" : pf >= 1.3 ? "Strong" : "Marginal"}
        />
        <MetricCard
          label="Sharpe-like"
          value={fmt(sharpe)}
          sub="EV / StdDev(R)"
          accent={sharpe > 0.5}
          warn={sharpe < 0}
        />
        <MetricCard
          label="Max Losing Streak"
          value={maxStreak}
          sub="Consecutive losses"
          warn={maxStreak >= 5}
        />
        <MetricCard
          label="Max Drawdown"
          value={`${fmt(maxDrawdownR)}R`}
          sub={`${fmt(analytics.maxDrawdownPct)}% from peak`}
          warn={analytics.maxDrawdownPct >= 8}
        />
        <MetricCard
          label="Risk of Ruin"
          value={rorDisplay}
          sub={isRorNA ? "< 10 trades" : "Est. probability"}
          warn={!isRorNA && ror != null && ror > 0.05}
        />
      </div>

      {/* Equity Curve */}
      <div style={{ marginBottom: 16 }}>
        <EquityCurveChart curve={curve} />
      </div>

      {/* Drawdown Chart */}
      {ddData && ddData.drawdownSeries && ddData.drawdownSeries.length > 1 && (
        <div style={{ marginBottom: 16 }}>
          <DrawdownChart series={ddData.drawdownSeries} />
        </div>
      )}

      {/* Distribution */}
      {distribution.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <DistributionChart distribution={distribution} />
        </div>
      )}

      {/* Validation Checklist */}
      <div style={{ marginBottom: 16 }}>
        <ValidationChecklist analytics={analytics} closedTrades={closedTrades} />
      </div>
    </div>
  );
}
