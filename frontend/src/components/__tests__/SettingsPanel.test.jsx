import { render, screen, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach } from "vitest";
import { mockSettings, mockHealth } from "../../test/api-mock";

vi.mock("../../api", () => ({
  api: {
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
    health: vi.fn(),
  },
}));

import SettingsPanel from "../SettingsPanel";
import { api } from "../../api";

beforeEach(() => {
  vi.clearAllMocks();
  api.getSettings.mockResolvedValue(mockSettings);
  api.health.mockResolvedValue(mockHealth);
});

describe("SettingsPanel", () => {
  it("renders system status card", async () => {
    render(<SettingsPanel />);
    await waitFor(() => {
      expect(screen.getByText("System Status")).toBeInTheDocument();
    });
    expect(screen.getByText(/Gold Intelligence System v4\.0/)).toBeInTheDocument();
  });

  it("shows system mode selector", async () => {
    render(<SettingsPanel />);
    await waitFor(() => {
      expect(screen.getByText("System Mode")).toBeInTheDocument();
    });
    // "Mode" appears in both the status grid and the form — verify at least one exists
    const modeElements = screen.getAllByText("Mode");
    expect(modeElements.length).toBeGreaterThanOrEqual(1);
  });

  it("shows safe mode selector", async () => {
    render(<SettingsPanel />);
    await waitFor(() => {
      expect(screen.getByText("Safe Mode (Kill Switch)")).toBeInTheDocument();
    });
  });

  it("shows account settings fields", async () => {
    render(<SettingsPanel />);
    await waitFor(() => {
      expect(screen.getByText("Account Equity (USD)")).toBeInTheDocument();
    });
    expect(screen.getByText("Risk Per Trade (%)")).toBeInTheDocument();
    expect(screen.getByText("Max Open Positions")).toBeInTheDocument();
  });

  it("has Save All button", async () => {
    render(<SettingsPanel />);
    expect(screen.getByRole("button", { name: /Save All/i })).toBeInTheDocument();
  });
});
