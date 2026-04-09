import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("Gold V1 execution workbench", () => {
  it("renders the project shell and switches views", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: /gold v1 execution workbench/i }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Rules" }));
    expect(
      screen.getByRole("heading", { name: /gold v1 — h4 pullback in trend/i }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Foundation" }));
    expect(
      screen.getByRole("heading", { name: /original written thesis, rendered for reading/i }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Journal" }));
    expect(
      screen.getByRole("heading", { name: /embedded execution journal/i }),
    ).toBeInTheDocument();
  });
});
