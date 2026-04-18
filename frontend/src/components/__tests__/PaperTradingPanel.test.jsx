import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import { mockPaperAccount, mockDecision, mockNoTradeDecision } from "../../test/api-mock";

vi.mock("../../api", () => ({
  api: {
    getPaperAccount: vi.fn(),
    getPaperPositions: vi.fn(),
    getPaperFills: vi.fn(),
    getPrice: vi.fn(),
    runDecision: vi.fn(),
    executePaperTrade: vi.fn(),
    closePaperPosition: vi.fn(),
  },
}));

import PaperTradingPanel from "../PaperTradingPanel";
import { api } from "../../api";

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  api.getPaperAccount.mockResolvedValue(mockPaperAccount);
  api.getPaperPositions.mockResolvedValue([]);
  api.getPaperFills.mockResolvedValue([]);
  api.getPrice.mockResolvedValue({ price: 3255.5, bid: 3255.3, ask: 3255.7, spread: 0.4 });
});

afterEach(() => {
  vi.useRealTimers();
});

describe("PaperTradingPanel", () => {
  it("shows PAPER MODE badge", async () => {
    render(<PaperTradingPanel onUpdate={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText("PAPER MODE")).toBeInTheDocument();
    });
  });

  it("renders account summary with balance and equity", async () => {
    render(<PaperTradingPanel onUpdate={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText("Balance")).toBeInTheDocument();
    });
    expect(screen.getByText("Equity")).toBeInTheDocument();
  });

  it("shows Run Decision button", async () => {
    render(<PaperTradingPanel onUpdate={() => {}} />);
    expect(screen.getByRole("button", { name: /Run Decision/i })).toBeInTheDocument();
  });

  it("execute button only appears after trade decision", async () => {
    api.runDecision.mockResolvedValue(mockDecision);

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<PaperTradingPanel onUpdate={() => {}} />);

    // No execute button initially
    expect(screen.queryByRole("button", { name: /Execute Paper Trade/i })).not.toBeInTheDocument();

    // Run decision that returns a trade signal
    await user.click(screen.getByRole("button", { name: /Run Decision/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Execute Paper Trade/i })).toBeInTheDocument();
    });
  });

  it("shows empty state when not connected", async () => {
    api.getPaperAccount.mockRejectedValue(new Error("offline"));
    api.getPaperPositions.mockRejectedValue(new Error("offline"));
    api.getPaperFills.mockRejectedValue(new Error("offline"));
    api.getPrice.mockRejectedValue(new Error("offline"));

    render(<PaperTradingPanel onUpdate={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(/Connect to the backend/)).toBeInTheDocument();
    });
  });
});
