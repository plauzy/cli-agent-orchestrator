import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { InstancePicker } from "../components/InstancePicker";
import { addInstance, listInstances } from "../instances";
import type { CaoInstance } from "../types";

// Review remediation (#387, Copilot inline): the remove control used to be an
// interactive element nested INSIDE the activate <button> — invalid HTML and
// broken for keyboard/AT users. These tests pin the sibling-buttons structure.

const INSTANCES: CaoInstance[] = [
  { id: "i1", url: "http://localhost:9889", label: "local", added_at: "2026-07-06T00:00:00Z" },
  { id: "i2", url: "http://remote:9889", label: "remote", added_at: "2026-07-06T00:00:00Z" },
];

function renderPicker(overrides: Partial<React.ComponentProps<typeof InstancePicker>> = {}) {
  const props = {
    instances: INSTANCES,
    activeId: "i1",
    onActivate: vi.fn(),
    onChanged: vi.fn(),
    ...overrides,
  };
  render(<InstancePicker {...props} />);
  return props;
}

describe("InstancePicker — a11y structure", () => {
  it("renders activate and remove as sibling buttons, never nested", () => {
    renderPicker();
    const activate = screen.getByRole("button", { name: "local" });
    const remove = screen.getByRole("button", { name: "Remove instance local" });
    expect(activate.contains(remove)).toBe(false);
    expect(remove.contains(activate)).toBe(false);
    // No interactive content inside any button (the original defect).
    for (const btn of screen.getAllByRole("button")) {
      expect(btn.querySelector("button, [role='button'], a[href], [tabindex]")).toBeNull();
    }
  });

  it("marks the active instance with aria-current", () => {
    renderPicker();
    expect(screen.getByRole("button", { name: "local" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: "remote" })).not.toHaveAttribute("aria-current");
  });

  it("activates on tab click without triggering removal", () => {
    const props = renderPicker();
    fireEvent.click(screen.getByRole("button", { name: "remote" }));
    expect(props.onActivate).toHaveBeenCalledWith("i2");
    expect(props.onChanged).not.toHaveBeenCalled();
  });

  it("removes the instance via its own button", async () => {
    const stored = await addInstance({ url: "http://localhost:9889", label: "local" });
    const props = renderPicker({
      instances: [{ ...stored }],
      activeId: stored.id,
    });
    fireEvent.click(screen.getByRole("button", { name: "Remove instance local" }));
    await waitFor(() => expect(props.onChanged).toHaveBeenCalled());
    expect(await listInstances()).toHaveLength(0);
  });
});
