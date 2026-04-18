import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, describe, it, expect, beforeEach } from "vitest";

// Mock child components so App tests focus on App shell behavior
vi.mock("../components/AnalysisPanel", () => ({
  default: () => <div data-testid="analysis-panel">Analysis Panel</div>,
}));
vi.mock("../components/StrategiesPanel", () => ({
  default: () => <div data-testid="strategies-panel">Strategies Panel</div>,
}));
vi.mock("../components/BacktestPanel", () => ({
  default: () => <div data-testid="backtest-panel">Backtest Panel</div>,
}));
vi.mock("../components/PaperTradingPanel", () => ({
  default: () => <div data-testid="paper-panel">Paper Panel</div>,
}));
vi.mock("../components/JournalPanel", () => ({
  default: () => <div data-testid="journal-panel">Journal Panel</div>,
}));
vi.mock("../components/MetricsPanel", () => ({
  default: () => <div data-testid="metrics-panel">Metrics Panel</div>,
}));
vi.mock("../components/SettingsPanel", () => ({
  default: () => <div data-testid="settings-panel">Settings Panel</div>,
}));

vi.mock("../api", () => ({
  api: {
    health: vi.fn(),
    getTrades: vi.fn(),
  },
}));

import App from "../App";
import { api } from "../api";

beforeEach(() => {
  vi.clearAllMocks();
  api.getTrades.mockResolvedValue([]);
});

describe("App", () => {
  it("renders the Gold Intelligence header", async () => {
    api.health.mockResolvedValue({
      status: "ok",
      has_api_key: true,
      system_mode: "paper_trading",
    });

    render(<App />);
    expect(screen.getByText("Gold Intelligence")).toBeInTheDocument();
    expect(screen.getByText("XAU / USD Trading Platform")).toBeInTheDocument();
  });

  it("shows all 7 navigation tabs", async () => {
    api.health.mockResolvedValue({
      status: "ok",
      has_api_key: true,
      system_mode: "paper_trading",
    });

    render(<App />);
    const tabLabels = ["Analysis", "Strategies", "Research", "Paper Trade", "Journal", "Metrics", "Settings"];
    for (const label of tabLabels) {
      expect(screen.getByRole("button", { name: new RegExp(label) })).toBeInTheDocument();
    }
  });

  it("defaults to Analysis view", async () => {
    api.health.mockResolvedValue({
      status: "ok",
      has_api_key: true,
      system_mode: "paper_trading",
    });

    render(<App />);
    expect(screen.getByTestId("analysis-panel")).toBeInTheDocument();
  });

  it("shows PAPER mode badge when system_mode is paper_trading", async () => {
    api.health.mockResolvedValue({
      status: "ok",
      has_api_key: true,
      system_mode: "paper_trading",
    });

    render(<App />);
    await waitFor(() => {
      expect(screen.getByText("PAPER")).toBeInTheDocument();
    });
  });

  it("shows DEMO badge when has_api_key is false", async () => {
    api.health.mockResolvedValue({
      status: "ok",
      has_api_key: false,
      system_mode: "paper_trading",
    });

    render(<App />);
    await waitFor(() => {
      expect(screen.getByText("DEMO")).toBeInTheDocument();
    });
  });

  it("shows Connected status when health check succeeds", async () => {
    api.health.mockResolvedValue({
      status: "ok",
      has_api_key: true,
      system_mode: "paper_trading",
    });

    render(<App />);
    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });
  });

  it("shows Offline when health check fails", async () => {
    api.health.mockRejectedValue(new Error("Network error"));

    render(<App />);
    await waitFor(() => {
      expect(screen.getByText("Offline")).toBeInTheDocument();
    });
  });

  it("can navigate between tabs by clicking them", async () => {
    api.health.mockResolvedValue({
      status: "ok",
      has_api_key: true,
      system_mode: "paper_trading",
    });

    const user = userEvent.setup();
    render(<App />);

    // Default is analysis
    expect(screen.getByTestId("analysis-panel")).toBeInTheDocument();

    // Click Strategies
    await user.click(screen.getByRole("button", { name: /Strategies/ }));
    expect(screen.getByTestId("strategies-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("analysis-panel")).not.toBeInTheDocument();

    // Click Settings
    await user.click(screen.getByRole("button", { name: /Settings/ }));
    expect(screen.getByTestId("settings-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("strategies-panel")).not.toBeInTheDocument();

    // Click back to Analysis
    await user.click(screen.getByRole("button", { name: /Analysis/ }));
    expect(screen.getByTestId("analysis-panel")).toBeInTheDocument();
  });
});
