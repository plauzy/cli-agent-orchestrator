import { describe, expect, it } from "vitest";
import { addInstance, listInstances, removeInstance } from "../instances";

describe("instances (IndexedDB CRUD)", () => {
  it("returns empty list when the store is fresh", async () => {
    expect(await listInstances()).toEqual([]);
  });

  it("persists an added instance with generated id + timestamp", async () => {
    const inst = await addInstance({ url: "http://localhost:9889", label: "local" });
    expect(inst.id).toBeTruthy();
    expect(inst.added_at).toBeTruthy();
    expect(inst.url).toBe("http://localhost:9889");
    expect(inst.label).toBe("local");

    const all = await listInstances();
    expect(all).toHaveLength(1);
    expect(all[0]).toEqual(inst);
  });

  it("removes by id", async () => {
    const a = await addInstance({ url: "http://a.example", label: "a" });
    const b = await addInstance({ url: "http://b.example", label: "b" });
    expect(await listInstances()).toHaveLength(2);

    await removeInstance(a.id);
    const remaining = await listInstances();
    expect(remaining).toHaveLength(1);
    expect(remaining[0].id).toBe(b.id);
  });
});
