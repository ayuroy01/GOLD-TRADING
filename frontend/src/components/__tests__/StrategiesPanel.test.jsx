import { render, screen, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach } from "vitest";
import {
  mockStrategies,
  mockRisk,
  mockRiskBlocked,
} from "../../test/api-mock";

vi.mock("../../api", () => ({
  api: {
    getStrategies: vi.fn(),
    getRisk: vi.fn(),
  },
}));

import StrategiesPanel from "../StrategiesPanel";
import { api } from "../../api";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("StrategiesPanel", () => {
  it("shows loading spinner initially", () => {
    // Never resolve so we stay in loading state
    api.getStrategies.mockReturnValue(new Promise(() => {}));
    api.getRisk.mockReturnValue(new Promise(() => {}));

    render(<StrategiesPanel />);
    expect(screen.getByText("Evaluating strategies...")).toBeInTheDocument();
  });

  it("renders strategy names after loading", async () => {
    api.getStrategies.mockResolvedValue(mockStrategies);
    api.getRisk.mockResolvedValue(mockRisk);

    render(<StrategiesPanel />);
    await waitFor(() => {
      expect(screen.getByText("trend_pullback")).toBeInTheDocument();
    });
    expect(screen.getByText("range_reversion")).toBeInTheDocument();
    expect(screen.getByText("breakout_compression")).toBeInTheDocument();
  });

  it("shows VALID SETUP badge for valid strategies", async () => {
    api.getStrategies.mockResolvedValue(mockStrategies);
    api.getRisk.mockResolvedValue(mockRisk);

    render(<StrategiesPanel />);
    await waitFor(() => {
      expect(screen.getByText("VALID SETUP")).toBeInTheDocument();
    });
  });

  it("shows NO SETUP badge for invalid strategies", async () => {
    api.getStrategies.mockResolvedValue(mockStrategies);
    api.getRisk.mockResolvedValue(mockRisk);

    render(<StrategiesPanel />);
    await waitFor(() => {
      const badges = screen.getAllByText("NO SETUP");
      expect(badges).toHaveLength(2);
    });
  });

  it("shows risk status CLEAR when trading is allowed", async () => {
    api.getStrategies.mockResolvedValue(mockStrategies);
    api.getRisk.mockResolvedValue(mockRisk);

    render(<StrategiesPanel />);
    await waitFor(() => {
      expect(screen.getByText("CLEAR")).toBeInTheDocument();
    });
    expect(screen.getByText("Trading allowed")).toBeInTheDocument();
  });

  it("shows risk status BLOCKED and blocker details when blocked", async () => {
    api.getStrategies.mockResolvedValue(mockStrategies);
    api.getRisk.mockResolvedValue(mockRiskBlocked);

    render(<StrategiesPanel />);
    await waitFor(() => {
      expect(screen.getByText("BLOCKED")).toBeInTheDocument();
    });
    expect(screen.getByText(/1 blocker\(s\) active/)).toBeInTheDocument();
    expect(screen.getByText(/Outside active trading sessions/)).toBeInTheDocument();
  });
});
