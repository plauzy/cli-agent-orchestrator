import "fake-indexeddb/auto";
import { afterEach } from "vitest";
import { clearInstances } from "../instances";

// Reset the IndexedDB store between tests so cross-test state doesn't
// leak. The fake-indexeddb backend stores per-process so a clear is
// enough; no need to tear down the whole DB.
afterEach(async () => {
  await clearInstances();
});

// jsdom doesn't ship HTMLDialogElement.showModal/close — minimal stub.
if (typeof HTMLDialogElement !== "undefined") {
  if (!HTMLDialogElement.prototype.showModal) {
    HTMLDialogElement.prototype.showModal = function () {
      this.setAttribute("open", "");
    };
  }
  if (!HTMLDialogElement.prototype.close) {
    HTMLDialogElement.prototype.close = function () {
      this.removeAttribute("open");
    };
  }
}
