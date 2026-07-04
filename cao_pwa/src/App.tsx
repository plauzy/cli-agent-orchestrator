import React, { useEffect, useState } from "react";
import { InstancePicker } from "./components/InstancePicker";
import { InstanceTab } from "./components/InstanceTab";
import { listInstances } from "./instances";
import type { CaoInstance } from "./types";

export function App() {
  const [instances, setInstances] = useState<CaoInstance[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void listInstances().then((items) => {
      setInstances(items);
      if (items.length > 0) setActive(items[0].id);
      setLoading(false);
    });
  }, []);

  const refresh = async () => {
    const items = await listInstances();
    setInstances(items);
    if (!items.find((i) => i.id === active) && items.length > 0) {
      setActive(items[0].id);
    } else if (items.length === 0) {
      setActive(null);
    }
  };

  if (loading) {
    return <div className="cao-pwa-root">Loading…</div>;
  }

  return (
    <div className="cao-pwa-root">
      <header className="cao-pwa-header">
        <h1>CAO Dashboard</h1>
        <InstancePicker
          instances={instances}
          activeId={active}
          onActivate={setActive}
          onChanged={refresh}
        />
      </header>
      <main>
        {active ? (
          <InstanceTab
            key={active}
            instance={instances.find((i) => i.id === active)!}
          />
        ) : (
          <p className="cao-pwa-empty">
            Add a CAO instance URL to get started. Operators running CAO
            locally can paste <code>http://localhost:9889</code>.
          </p>
        )}
      </main>
    </div>
  );
}
