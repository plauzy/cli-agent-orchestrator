import time

import requests


class CAOClient:
    def __init__(self, base_url: str = "http://localhost:9889", timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def health_check(self) -> bool:
        resp = requests.get(f"{self.base_url}/health", timeout=5)
        resp.raise_for_status()
        return resp.json().get("status") == "ok"

    def create_terminal(
        self,
        session_name: str,
        provider: str = "claude_code",
        agent_profile: str = "developer",
    ) -> str:
        # Clean up any stale session from a prior run
        requests.delete(f"{self.base_url}/sessions/{session_name}", timeout=5)

        resp = requests.post(
            f"{self.base_url}/sessions",
            params={
                "provider": provider,
                "agent_profile": agent_profile,
                "session_name": session_name,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def dispatch_task(
        self,
        terminal_id: str,
        message: str,
        orchestration_type: str = "send_message",
    ) -> None:
        resp = requests.post(
            f"{self.base_url}/terminals/{terminal_id}/input",
            params={"message": message, "orchestration_type": orchestration_type},
            timeout=30,
        )
        resp.raise_for_status()

    def poll_completion(self, terminal_id: str, poll_interval: float = 3.0) -> tuple[str, float]:
        start = time.time()
        seen_active = False
        time.sleep(2.0)  # let dispatch propagate before first poll
        while True:
            elapsed = time.time() - start
            if elapsed > self.timeout:
                raise TimeoutError(
                    f"Terminal {terminal_id} did not complete within {self.timeout}s"
                )

            resp = requests.get(f"{self.base_url}/terminals/{terminal_id}", timeout=10)
            resp.raise_for_status()
            status = resp.json().get("status", "")

            if status not in ("idle",):
                seen_active = True

            if status in ("completed", "error") or (status == "idle" and seen_active):
                out = requests.get(
                    f"{self.base_url}/terminals/{terminal_id}/output",
                    params={"mode": "full"},
                    timeout=10,
                )
                out.raise_for_status()
                return out.json().get("output", ""), elapsed

            time.sleep(poll_interval)

    def cleanup(self, session_name: str) -> None:
        requests.delete(f"{self.base_url}/sessions/{session_name}", timeout=10)
