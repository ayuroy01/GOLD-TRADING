import { render, screen } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach } from "vitest";
import { mockTrades } from "../../test/api-mock";

vi.mock("../../api", () => ({
  api: {
    updateTrade: vi.fn(),
    deleteTrade: vi.fn(),
  },
}));

import JournalPanel from "../JournalPanel";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("JournalPanel", () => {
  it("shows empty state when no trades", () => {
    render(<JournalPanel trades={[]} onUpdate={() => {}} />);
    expect(screen.getByText("No trades logged")).toBeInTheDocument();
  });

  it("renders trade table when trades exist", () => {
    render(<JournalPanel trades={mockTrades} onUpdate={() => {}} />);
    expect(screen.getByText("Trade Journal")).toBeInTheDocument();
    // Check that trade data appears in the table
    expect(screen.getByText("LONG")).toBeInTheDocument();
    expect(screen.getByText("SHORT")).toBeInTheDocument();
  });

  it("shows filter tabs (All, Open, Closed)", () => {
    render(<JournalPanel trades={mockTrades} onUpdate={() => {}} />);
    expect(screen.getByRole("button", { name: /^All$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Open$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Closed$/i })).toBeInTheDocument();
  });

  it("shows Close button for open trades", () => {
    render(<JournalPanel trades={mockTrades} onUpdate={() => {}} />);
    // mockTrades[0] is open, so there should be a Close button
    const closeButtons = screen.getAllByRole("button", { name: /^Close$/i });
    expect(closeButtons.length).toBeGreaterThanOrEqual(1);
  });

  it("shows delete button", () => {
    render(<JournalPanel trades={mockTrades} onUpdate={() => {}} />);
    // Delete buttons use the x character
    const deleteButtons = screen.getAllByRole("button", { name: /\u00d7/ });
    expect(deleteButtons.length).toBeGreaterThanOrEqual(1);
  });
});
