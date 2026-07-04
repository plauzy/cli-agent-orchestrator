import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { GenerativeUI, SUPPORTED_COMPONENTS } from "../components/GenerativeUI";

describe("GenerativeUI — safe, allow-listed rendering", () => {
  it("renders an approval_card with title and actions", () => {
    render(
      <GenerativeUI
        data={{ component: "approval_card", props: { title: "Approve handoff?", risk: "high" } }}
      />,
    );
    expect(screen.getByText("Approve handoff?")).toBeInTheDocument();
    expect(screen.getByText(/high risk/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
  });

  it("wires approval actions to the onAction handler", () => {
    const onAction = vi.fn();
    render(
      <GenerativeUI
        data={{ component: "approval_card", props: { title: "Ship it?" } }}
        onAction={onAction}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(onAction).toHaveBeenCalledWith("approve", expect.objectContaining({ title: "Ship it?" }));
  });

  it("disables actions when read-only (no onAction)", () => {
    render(<GenerativeUI data={{ component: "approval_card", props: { title: "x" } }} />);
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
  });

  it("renders a choice_prompt with one button per choice", () => {
    const onAction = vi.fn();
    render(
      <GenerativeUI
        data={{ component: "choice_prompt", props: { question: "Which model?", choices: ["opus", "sonnet"] } }}
        onAction={onAction}
      />,
    );
    expect(screen.getByText("Which model?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "sonnet" }));
    expect(onAction).toHaveBeenCalledWith("choose", { value: "sonnet" });
  });

  it("renders a diff_summary with per-file add/del counts", () => {
    render(
      <GenerativeUI
        data={{
          component: "diff_summary",
          props: { title: "PR #8", files: [{ path: "api/main.py", additions: 12, deletions: 3 }] },
        }}
      />,
    );
    expect(screen.getByText("api/main.py")).toBeInTheDocument();
    expect(screen.getByText("+12")).toBeInTheDocument();
    expect(screen.getByText("-3")).toBeInTheDocument();
  });

  it("renders a determinate progress bar", () => {
    render(<GenerativeUI data={{ component: "progress", props: { label: "Indexing", value: 0.4 } }} />);
    expect(screen.getByText("Indexing")).toBeInTheDocument();
    const bar = document.querySelector("progress") as HTMLProgressElement;
    expect(bar).toBeTruthy();
    expect(bar.value).toBeCloseTo(0.4);
  });

  it("renders a metric with value and unit", () => {
    render(<GenerativeUI data={{ component: "metric", props: { label: "throughput", value: 42, unit: "tok/s" } }} />);
    expect(screen.getByText("throughput")).toBeInTheDocument();
    expect(screen.getByText(/42/)).toBeInTheDocument();
    expect(screen.getByText(/tok\/s/)).toBeInTheDocument();
  });

  it("renders an agent_card uniformly regardless of provider", () => {
    render(
      <GenerativeUI data={{ component: "agent_card", props: { name: "reviewer", provider: "q_cli", status: "running" } }} />,
    );
    expect(screen.getByText("reviewer")).toBeInTheDocument();
    expect(screen.getByText("q_cli")).toBeInTheDocument();
  });

  it("REFUSES an unknown/unsafe component (renders inert placeholder, no markup)", () => {
    const { container } = render(
      <GenerativeUI data={{ component: "iframe", props: { src: "http://evil" } }} />,
    );
    expect(screen.getByText(/unsupported component/i)).toBeInTheDocument();
    // No iframe is ever created from an agent-chosen component name.
    expect(container.querySelector("iframe")).toBeNull();
  });

  it("exposes a client allow-list of exactly the supported components", () => {
    expect([...SUPPORTED_COMPONENTS].sort()).toEqual(
      ["agent_card", "approval_card", "choice_prompt", "diff_summary", "metric", "progress"].sort(),
    );
  });
});
