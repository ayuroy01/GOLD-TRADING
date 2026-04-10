import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, beforeEach } from "vitest";
import App from "./App";

// Mock localStorage for test environment
const store = {};
beforeEach(() => {
  Object.keys(store).forEach(k => delete store[k]);
  Object.defineProperty(window, "localStorage", {
    value: {
      getItem: (key) => store[key] || null,
      setItem: (key, value) => { store[key] = String(value); },
      removeItem: (key) => { delete store[key]; },
      clear: () => { Object.keys(store).forEach(k => delete store[k]); },
    },
    writable: true,
  });
});

describe("Gold V1 Execution System", () => {
  it("renders the app shell with brand title", () => {
    render(<App />);
    expect(screen.getByText("Gold V1")).toBeInTheDocument();
    expect(screen.getByText("XAU/USD Execution System")).toBeInTheDocument();
  });

  it("shows Execute view by default with active styling", () => {
    render(<App />);
    const allNavBtns = screen.getAllByText(/Execute|Analytics|Journal|Rules|Foundation/);
    const executeBtn = allNavBtns.find(el => el.textContent.includes("Execute") && el.classList.contains("nav-btn"));
    expect(executeBtn).toBeTruthy();
    expect(executeBtn.className).toContain("active");
  });

  it("switches to Rules view on click", () => {
    render(<App />);
    const allBtns = document.querySelectorAll(".nav-btn");
    const rulesBtn = Array.from(allBtns).find(b => b.textContent.includes("Rules"));
    fireEvent.click(rulesBtn);
    expect(screen.getByText(/System Specification/i)).toBeInTheDocument();
  });
});
