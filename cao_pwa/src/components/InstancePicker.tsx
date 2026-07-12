import React, { useRef, useState } from "react";
import { addInstance, removeInstance } from "../instances";
import { pingInstance } from "../api";
import type { CaoInstance } from "../types";

interface Props {
  instances: CaoInstance[];
  activeId: string | null;
  onActivate(id: string): void;
  onChanged(): void | Promise<void>;
}

export function InstancePicker({ instances, activeId, onActivate, onChanged }: Props) {
  const [url, setUrl] = useState("http://localhost:9889");
  const [label, setLabel] = useState("local");
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);

  const open = () => {
    setError(null);
    dialogRef.current?.showModal();
  };
  const close = () => dialogRef.current?.close();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAdding(true);
    setError(null);
    try {
      new URL(url); // validate URL shape
    } catch {
      setError("Not a valid URL");
      setAdding(false);
      return;
    }
    const reachable = await pingInstance(url);
    if (!reachable) {
      setError(`Could not reach ${url}/health — add anyway?`);
      // Don't return — allow adding even if unreachable; user may
      // want to add a remote instance that's currently offline.
    }
    await addInstance({ url, label: label || url });
    await onChanged();
    close();
    setAdding(false);
  };

  const remove = async (id: string) => {
    await removeInstance(id);
    await onChanged();
  };

  return (
    <>
      <nav className="cao-pwa-nav" aria-label="CAO instances">
        {/* The activate and remove controls are sibling <button>s (grouped by
            the wrapper) — interactive content inside a <button> is invalid
            HTML and unreachable for keyboard/AT users. */}
        {instances.map((inst) => (
          <span key={inst.id} className="cao-pwa-tabitem" role="group" aria-label={inst.label}>
            <button
              type="button"
              className={inst.id === activeId ? "active" : ""}
              onClick={() => onActivate(inst.id)}
              aria-current={inst.id === activeId ? "page" : undefined}
            >
              {inst.label}
            </button>
            <button
              type="button"
              className="cao-pwa-remove"
              aria-label={`Remove instance ${inst.label}`}
              onClick={() => void remove(inst.id)}
            >
              ×
            </button>
          </span>
        ))}
        <button type="button" onClick={open} aria-label="Add CAO instance">
          + Add instance
        </button>
      </nav>

      <dialog
        ref={dialogRef}
        className="cao-pwa-dialog"
        aria-labelledby="cao-pwa-add-title"
      >
        <form method="dialog" onSubmit={submit}>
          <h2 id="cao-pwa-add-title">Add CAO instance</h2>
          <label>
            URL
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
              autoFocus
              placeholder="http://localhost:9889"
            />
          </label>
          <label>
            Label
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="local"
            />
          </label>
          {error && <p className="cao-pwa-error">{error}</p>}
          <div className="cao-pwa-actions">
            <button type="button" onClick={close}>
              Cancel
            </button>
            <button type="submit" disabled={adding}>
              {adding ? "Adding…" : "Add"}
            </button>
          </div>
        </form>
      </dialog>
    </>
  );
}
