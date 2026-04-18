import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, describe, it, expect, beforeEach } from "vitest";

vi.mock("react-markdown", () => ({
  default: ({ children }) => <div data-testid="markdown">{children}</div>,
}));
vi.mock("remark-gfm", () => ({ default: () => {} }));

vi.mock("../../api", () => ({
  api: {
    getPrice: vi.fn(),
    getMacro: vi.fn(),
    getCalendar: vi.fn(),
    runAnalysis: vi.fn(),
    getAnalysisLog: vi.fn(),
  },
}));

import AnalysisPanel from "../AnalysisPanel";
import { api } from "../../api";

beforeEach(() => {
  vi.clearAllMocks();
  api.getPrice.mockResolvedValue({ price: 3255.5, spread: 0.4, source: "simulated" });
  api.getMacro.mockResolvedValue({ usd_index: 103.5, usd_regime: "neutral", treasury_10y: 4.2, rate_direction: "stable", gold_macro_bias: "neutral", geopolitical_risk: "moderate" });
  api.getCalendar.mockResolvedValue({ events: [], high_impact_within_2h: false, nearest_high_impact: null });
  api.getAnalysisLog.mockResolvedValue([]);
});

describe("AnalysisPanel", () => {
  it("renders Run Analysis button", async () => {
    render(<AnalysisPanel />);
    expect(screen.getByRole("button", { name: /Run Analysis/i })).toBeInTheDocument();
  });

  it("shows empty state when no analysis exists", async () => {
    render(<AnalysisPanel />);
    await waitFor(() => {
      expect(screen.getByText("No analysis yet")).toBeInTheDocument();
    });
  });

  it("shows loading state during analysis", async () => {
    // Make runAnalysis hang
    api.runAnalysis.mockReturnValue(new Promise(() => {}));

    const user = userEvent.setup();
    render(<AnalysisPanel />);

    await user.click(screen.getByRole("button", { name: /Run Analysis/i }));

    expect(screen.getByText("Analyzing...")).toBeInTheDocument();
    expect(screen.getByText(/Fetching market data/)).toBeInTheDocument();
  });

  it("shows error message when analysis fails", async () => {
    api.runAnalysis.mockRejectedValue(new Error("API timeout"));

    const user = userEvent.setup();
    render(<AnalysisPanel />);

    await user.click(screen.getByRole("button", { name: /Run Analysis/i }));

    await waitFor(() => {
      expect(screen.getByText("API timeout")).toBeInTheDocument();
    });
  });

  it("displays analysis result after successful run", async () => {
    api.runAnalysis.mockResolvedValue({
      analysis: "## Bullish setup detected",
      iterations: 1,
      timestamp: "2024-01-15T12:00:00Z",
      model: "rule-based (demo)",
    });

    const user = userEvent.setup();
    render(<AnalysisPanel />);

    await user.click(screen.getByRole("button", { name: /Run Analysis/i }));

    await waitFor(() => {
      expect(screen.getByText("Analysis Result")).toBeInTheDocument();
    });
    expect(screen.getByText("## Bullish setup detected")).toBeInTheDocument();
    expect(screen.getByText(/rule-based \(demo\)/)).toBeInTheDocument();
  });
});
