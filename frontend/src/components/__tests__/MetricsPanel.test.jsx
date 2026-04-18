import { render, screen, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach } from "vitest";
import { mockMetrics } from "../../test/api-mock";

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
    getMetrics: vi.fn(),
  },
}));

import MetricsPanel from "../MetricsPanel";
import { api } from "../../api";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("MetricsPanel", () => {
  it("shows loading state initially", () => {
    api.getMetrics.mockReturnValue(new Promise(() => {}));
    render(<MetricsPanel trades={[]} />);
    expect(screen.getByText("Loading metrics...")).toBeInTheDocument();
  });

  it("shows empty state when no closed trades", async () => {
    api.getMetrics.mockResolvedValue({ closed_trades: 0 });
    render(<MetricsPanel trades={[]} />);
    await waitFor(() => {
      expect(screen.getByText("No analytics yet")).toBeInTheDocument();
    });
  });

  it("renders metrics cards when data exists", async () => {
    api.getMetrics.mockResolvedValue(mockMetrics);
    render(<MetricsPanel trades={[{ id: 1 }]} />);
    await waitFor(() => {
      expect(screen.getByText("Total Trades")).toBeInTheDocument();
    });
    expect(screen.getByText("Win Rate")).toBeInTheDocument();
    expect(screen.getByText("Expectancy")).toBeInTheDocument();
    expect(screen.getByText("Profit Factor")).toBeInTheDocument();
    expect(screen.getByText("Sharpe")).toBeInTheDocument();
    expect(screen.getByText("Max Drawdown")).toBeInTheDocument();
    expect(screen.getByText("Edge Status")).toBeInTheDocument();
    expect(screen.getByText("Collecting data")).toBeInTheDocument();
  });
});
