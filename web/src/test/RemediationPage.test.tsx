import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { RemediationPage } from "../pages/RemediationPage";

describe("RemediationPage", () => {
  it("shows plan-only policy without execute controls", () => {
    render(
      <MemoryRouter>
        <RemediationPage />
      </MemoryRouter>,
    );
    expect(screen.getByText("Plan only")).toBeInTheDocument();
    expect(screen.getByText("Human approval required")).toBeInTheDocument();
    expect(screen.getByText("Auto execution disabled")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /execute/i })).not.toBeInTheDocument();
  });
});
