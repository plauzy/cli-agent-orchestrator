// IndexedDB CRUD for the multi-instance CAO list.
//
// Why IndexedDB and not localStorage: cross-tab consistency, larger
// quota, async API plays better with React. Per v2 plan §13 the iframe
// can't use storage at all; the PWA at its own origin has no such
// constraint.

import type { CaoInstance } from "./types";

const DB_NAME = "cao_pwa";
const DB_VERSION = 1;
const STORE = "instances";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "id" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function txn<T>(
  mode: IDBTransactionMode,
  body: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  return openDb().then(
    (db) =>
      new Promise<T>((resolve, reject) => {
        const tx = db.transaction(STORE, mode);
        const store = tx.objectStore(STORE);
        const req = body(store);
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
      }),
  );
}

export async function listInstances(): Promise<CaoInstance[]> {
  const result = await txn<CaoInstance[]>("readonly", (s) => s.getAll());
  return result ?? [];
}

export async function addInstance(
  instance: Omit<CaoInstance, "id" | "added_at"> & { id?: string },
): Promise<CaoInstance> {
  const record: CaoInstance = {
    id: instance.id ?? crypto.randomUUID(),
    url: instance.url,
    label: instance.label,
    added_at: new Date().toISOString(),
  };
  await txn("readwrite", (s) => s.put(record));
  return record;
}

export async function removeInstance(id: string): Promise<void> {
  await txn("readwrite", (s) => s.delete(id));
}

export async function clearInstances(): Promise<void> {
  await txn("readwrite", (s) => s.clear());
}
