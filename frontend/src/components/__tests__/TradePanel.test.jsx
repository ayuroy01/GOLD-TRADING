import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach } from "vitest";
import { mockSettings, mockTrades } from "../../test/api-mock";

vi.mock("../../api", () => ({
  api: {
    getSettings: vi.fn(),
    logTrade: vi.fn(),
  },
}));

import TradePanel from "../TradePanel";
import { api } from "../../api";

beforeEach(() => {
  vi.clearAllMocks();
  api.getSettings.mockResolvedValue(mockSettings);
  api.logTrade.mockResolvedValue({ id: 9999 });
});

describe("TradePanel", () => {
  it("renders form fields", () => {
    render(<TradePanel trades={[]} onUpdate={() => {}} />);

    expect(screen.getByText("Entry Price")).toBeInTheDocument();
    expect(screen.getByText("Stop Loss")).toBeInTheDocument();
    expect(screen.getByText("Target 1")).toBeInTheDocument();
    expect(screen.getByText("Target 2")).toBeInTheDocument();
    expect(screen.getByText("Pullback Zone")).toBeInTheDocument();
    expect(screen.getByText("Entry Trigger")).toBeInTheDocument();
    expect(screen.getByText("Notes")).toBeInTheDocument();
  });

  it("shows computed values when entry and stop are filled", () => {
    render(<TradePanel trades={[]} onUpdate={() => {}} />);

    const entryInput = screen.getByPlaceholderText("3245.50");
    const stopInput = screen.getByPlaceholderText("3228.00");

    fireEvent.change(entryInput, { target: { value: "3250" } });
    fireEvent.change(stopInput, { target: { value: "3240" } });

    expect(screen.getByText("LONG")).toBeInTheDocument();
    expect(screen.getByText("Risk Distance")).toBeInTheDocument();
    expect(screen.getByText("Risk USD")).toBeInTheDocument();
    expect(screen.getByText("Position")).toBeInTheDocument();
  });

  it("shows R:R validation warning below 1.5", () => {
    render(<TradePanel trades={[]} onUpdate={() => {}} />);

    const entryInput = screen.getByPlaceholderText("3245.50");
    const stopInput = screen.getByPlaceholderText("3228.00");
    const t1Input = screen.getByPlaceholderText("3270.00");

    fireEvent.change(entryInput, { target: { value: "3250" } });
    fireEvent.change(stopInput, { target: { value: "3240" } });
    fireEvent.change(t1Input, { target: { value: "3255" } });

    // R:R = |3255 - 3250| / |3250 - 3240| = 5/10 = 0.5
    expect(screen.getByText(/minimum 1\.5:1/)).toBeInTheDocument();
  });

  it("disables submit when no prices entered", () => {
    render(<TradePanel trades={[]} onUpdate={() => {}} />);

    const button = screen.getByRole("button", { name: /Log Trade/i });
    expect(button).toBeDisabled();
  });

  it("disables submit when R:R validation fails", () => {
    render(<TradePanel trades={[]} onUpdate={() => {}} />);

    const entryInput = screen.getByPlaceholderText("3245.50");
    const stopInput = screen.getByPlaceholderText("3228.00");
    const t1Input = screen.getByPlaceholderText("3270.00");

    fireEvent.change(entryInput, { target: { value: "3250" } });
    fireEvent.change(stopInput, { target: { value: "3240" } });
    fireEvent.change(t1Input, { target: { value: "3255" } });

    const button = screen.getByRole("button", { name: /Log Trade/i });
    expect(button).toBeDisabled();
  });

  it("disables submit when max positions reached", () => {
    const twoOpenTrades = [
      { ...mockTrades[0], id: 1, status: "open" },
      { ...mockTrades[0], id: 2, status: "open" },
    ];

    render(<TradePanel trades={twoOpenTrades} onUpdate={() => {}} />);

    const entryInput = screen.getByPlaceholderText("3245.50");
    const stopInput = screen.getByPlaceholderText("3228.00");
    const t1Input = screen.getByPlaceholderText("3270.00");

    fireEvent.change(entryInput, { target: { value: "3250" } });
    fireEvent.change(stopInput, { target: { value: "3240" } });
    fireEvent.change(t1Input, { target: { value: "3270" } });

    const button = screen.getByRole("button", { name: /Log Trade/i });
    expect(button).toBeDisabled();
    expect(screen.getByText(/max 2/)).toBeInTheDocument();
  });

  it("enables submit with valid trade", () => {
    render(<TradePanel trades={[]} onUpdate={() => {}} />);

    const entryInput = screen.getByPlaceholderText("3245.50");
    const stopInput = screen.getByPlaceholderText("3228.00");
    const t1Input = screen.getByPlaceholderText("3270.00");

    fireEvent.change(entryInput, { target: { value: "3250" } });
    fireEvent.change(stopInput, { target: { value: "3240" } });
    fireEvent.change(t1Input, { target: { value: "3270" } });

    // R:R = |3270 - 3250| / |3250 - 3240| = 20/10 = 2.0 (>= 1.5, valid)
    const button = screen.getByRole("button", { name: /Log Trade/i });
    expect(button).not.toBeDisabled();
  });

  it("calls api.logTrade on submit", async () => {
    const onUpdate = vi.fn();
    render(<TradePanel trades={[]} onUpdate={onUpdate} />);

    const entryInput = screen.getByPlaceholderText("3245.50");
    const stopInput = screen.getByPlaceholderText("3228.00");
    const t1Input = screen.getByPlaceholderText("3270.00");

    fireEvent.change(entryInput, { target: { value: "3250" } });
    fireEvent.change(stopInput, { target: { value: "3240" } });
    fireEvent.change(t1Input, { target: { value: "3270" } });

    const button = screen.getByRole("button", { name: /Log Trade/i });
    fireEvent.click(button);

    await waitFor(() => {
      expect(api.logTrade).toHaveBeenCalledTimes(1);
    });

    const call = api.logTrade.mock.calls[0][0];
    expect(call.direction).toBe("long");
    expect(call.entry).toBe(3250);
    expect(call.stop).toBe(3240);
    expect(call.t1).toBe(3270);
    expect(call.risk_distance).toBe(10);
    expect(call.rr_to_t1).toBe(2);
    expect(call.status).toBe("open");
  });
});
