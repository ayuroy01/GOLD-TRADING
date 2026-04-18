import { render, screen } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach } from "vitest";

vi.mock("recharts", () => ({
  LineChart: ({ children }) => <div>{children}</div>,
  Line: () => null,
  BarChart: ({ children }) => <div>{children}</div>,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }) => <div>{children}</div>,
  ReferenceLine: () => null,
  Cell: () => null,
}));

vi.mock("../../api", () => ({
  api: {
    runBacktest: vi.fn(),
    runWalkForward: vi.fn(),
  },
}));

import BacktestPanel from "../BacktestPanel";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("BacktestPanel", () => {
  it("renders backtest controls (candles, spread, folds inputs)", () => {
    render(<BacktestPanel />);
    // Labels are rendered as text, inputs are present by their displayed values
    expect(screen.getByText("Candles (1h)")).toBeInTheDocument();
    expect(screen.getByText("Spread ($)")).toBeInTheDocument();
    expect(screen.getByText("Walk-Forward Folds")).toBeInTheDocument();
    expect(screen.getByDisplayValue("500")).toBeInTheDocument();
    expect(screen.getByDisplayValue("0.40")).toBeInTheDocument();
    expect(screen.getByDisplayValue("3")).toBeInTheDocument();
  });

  it("shows empty state initially", () => {
    render(<BacktestPanel />);
    expect(screen.getByText("No research results yet")).toBeInTheDocument();
  });

  it("shows Run Backtest and Walk-Forward Test buttons", () => {
    render(<BacktestPanel />);
    expect(screen.getByRole("button", { name: /Run Backtest/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Walk-Forward Test/i })).toBeInTheDocument();
  });

  it("shows disclaimer text about simulated data", () => {
    render(<BacktestPanel />);
    expect(screen.getByText(/Data is simulated/i)).toBeInTheDocument();
    expect(screen.getByText(/do not represent real market performance/i)).toBeInTheDocument();
  });
});
