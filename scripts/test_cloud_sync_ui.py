"""Browser-level regression test for OmniShelf's account/cloud-sync UI.

This deliberately uses a local mocked API. It never connects to Render or Neon,
creates accounts, or writes to a hosted library. Backend/security behaviour is
covered separately by the API and PostgreSQL integration suites.
"""
from __future__ import annotations

import copy
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
FIXTURE_PASSWORD = "local-ui-fixture-password"
RESTORED_TITLE = "Cloud Restore QA — canonical library"

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


class MockCloudAPI:
    def __init__(self) -> None:
        self.authenticated = False
        self.revision = 0
        self.snapshot_state: dict | None = None
        self.user = {
            "id": "local-ui-test-account",
            "username": "test-reader",
            "email": "test-reader@example.invalid",
            "created_at": "2026-10-16T00:00:00Z",
        }
        self.requests: list[tuple[str, str]] = []

    @staticmethod
    def respond(route, payload: dict, status: int = 200) -> None:
        route.fulfill(
            status=status,
            content_type="application/json",
            headers={"Cache-Control": "no-store"},
            body=json.dumps(payload),
        )

    def handle(self, route) -> None:
        request = route.request
        method = request.method.upper()
        path = urlparse(request.url).path
        self.requests.append((method, path))

        if path == "/api/auth/me" and method == "GET":
            self.respond(route, {"user": self.user if self.authenticated else None})
            return

        if path == "/api/auth/login" and method == "POST":
            payload = request.post_data_json or {}
            if (
                payload.get("identifier", "").strip().lower() == self.user["username"]
                and payload.get("password") == FIXTURE_PASSWORD
            ):
                self.authenticated = True
                self.respond(route, {"user": self.user})
            else:
                self.respond(route, {"detail": "The username/email or password was incorrect."}, 401)
            return

        if path == "/api/auth/logout" and method == "POST":
            self.authenticated = False
            route.fulfill(status=204, body="")
            return

        if path.startswith("/api/me/state"):
            if not self.authenticated:
                self.respond(route, {"detail": "Sign in to access your cloud library."}, 401)
                return

            if path == "/api/me/state/meta" and method == "GET":
                current = self.snapshot_state
                self.respond(route, {
                    "exists": current is not None,
                    "revision": self.revision,
                    "updated_at": "2026-10-16T00:00:00Z" if current is not None else None,
                    "work_count": len(current.get("works", [])) if current else 0,
                    "review_count": len(current.get("reviews", [])) if current else 0,
                })
                return

            if path == "/api/me/state" and method == "GET":
                self.respond(route, {
                    "exists": self.snapshot_state is not None,
                    "revision": self.revision,
                    "updated_at": "2026-10-16T00:00:00Z" if self.snapshot_state is not None else None,
                    "state": copy.deepcopy(self.snapshot_state),
                })
                return

            if path == "/api/me/state" and method == "PUT":
                payload = request.post_data_json or {}
                if payload.get("expected_revision") != self.revision:
                    self.respond(route, {"detail": "Cloud revision conflict."}, 409)
                    return
                state = payload.get("state")
                if not isinstance(state, dict) or not isinstance(state.get("profile"), dict) or not isinstance(state.get("works"), list):
                    self.respond(route, {"detail": "Invalid cloud state fixture."}, 422)
                    return
                self.snapshot_state = copy.deepcopy(state)
                self.revision += 1
                self.respond(route, {
                    "exists": True,
                    "revision": self.revision,
                    "updated_at": "2026-10-16T00:00:00Z",
                    "work_count": len(state.get("works", [])),
                    "review_count": len(state.get("reviews", [])),
                })
                return

        self.respond(route, {"detail": f"Unexpected mocked API request: {method} {path}"}, 404)


def main() -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    handler = partial(QuietHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    api = MockCloudAPI()
    browser = None
    page_errors: list[str] = []

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.route("**/api/**", api.handle)
            page.goto(f"http://127.0.0.1:{server.server_port}/index.html", wait_until="domcontentloaded")
            page.locator("#cloudAccountBtn").wait_for(state="visible", timeout=10000)
            page.wait_for_timeout(300)

            # Anonymous access should show the sign-in screen; no public signup call is made.
            page.locator("#cloudAccountBtn").click()
            page.locator("#cloudAuthForm").wait_for(state="visible", timeout=5000)
            page.locator("#cloudIdentifier").fill("test-reader")
            page.locator("#cloudPassword").fill(FIXTURE_PASSWORD)
            page.locator("#cloudAuthSubmit").click()
            page.get_by_text("@test-reader", exact=True).wait_for(timeout=10000)
            page.get_by_text("Not uploaded yet", exact=True).wait_for(timeout=5000)

            # Preserve a real screenshot of the authenticated UI fixture for the build artifact.
            page.screenshot(path=str(ARTIFACTS / "omnishelf-1.3.8-cloud-sync-connected.png"), full_page=True)

            dialogs = []
            page.on("dialog", lambda dialog: (dialogs.append(dialog.message), dialog.accept()))
            page.locator("#cloudUploadBtn").click()
            page.get_by_text("Cloud snapshot saved as revision 1.", exact=True).wait_for(timeout=10000)
            assert api.revision == 1, f"Expected first upload to create revision 1, got {api.revision}"
            assert api.snapshot_state is not None
            assert isinstance(api.snapshot_state.get("profile"), dict)
            assert isinstance(api.snapshot_state.get("works"), list)
            assert any(method == "PUT" and path == "/api/me/state" for method, path in api.requests)

            # Simulate another device winning the race. The stale local revision must be rejected.
            assert api.snapshot_state is not None
            local_state = copy.deepcopy(api.snapshot_state)
            remote_state = copy.deepcopy(api.snapshot_state)
            remote_state["profile"] = dict(remote_state.get("profile") or {})
            remote_state["profile"]["name"] = "Cloud Restore QA"
            works = list(remote_state.get("works") or [])
            if works:
                works[0] = dict(works[0])
                works[0]["title"] = RESTORED_TITLE
                remote_state["works"] = works[:1]
            else:
                remote_state["works"] = [{
                    "id": "cloud-restore-qa",
                    "title": RESTORED_TITLE,
                    "medium": "Novella",
                    "status": "In Progress",
                    "progress": 0,
                    "score": 0,
                }]
            api.revision = 2
            api.snapshot_state = remote_state

            page.locator("#cloudUploadBtn").click()
            page.get_by_text("A newer cloud revision exists. Restore it or review it before uploading again.", exact=True).wait_for(timeout=10000)
            assert api.revision == 2, "A stale upload must not advance the mocked cloud revision."
            assert api.snapshot_state == remote_state, "A stale upload must not overwrite the newer remote snapshot."

            # Restore the new remote version and check that the browser copy changes.
            page.locator("#cloudRestoreBtn").click()
            page.get_by_text("Restored cloud revision 2 to this browser.", exact=True).wait_for(timeout=10000)
            restored = page.evaluate("""() => {
                const raw = localStorage.getItem('omnishelf-state');
                return raw ? JSON.parse(raw) : null;
            }""")
            assert restored and isinstance(restored.get("works"), list), "Restored library was not saved locally."
            assert any(work.get("title") == RESTORED_TITLE for work in restored["works"]), (
                "Restore should replace the browser library with the latest cloud snapshot."
            )

            # Sign-out must return to sign-in while leaving local-only data intact.
            page.locator("#cloudLogoutBtn").click()
            page.get_by_text("Signed out. Your local browser data remains available.", exact=True).wait_for(timeout=10000)
            after_logout = page.evaluate("""() => {
                const raw = localStorage.getItem('omnishelf-state');
                return raw ? JSON.parse(raw) : null;
            }""")
            assert after_logout and any(work.get("title") == RESTORED_TITLE for work in after_logout.get("works", [])), (
                "Signing out must not delete the browser's local library."
            )
            assert not api.authenticated, "Mock API should revoke its signed-in session on logout."
            assert not any(method == "POST" and path == "/api/auth/register" for method, path in api.requests), (
                "The browser acceptance test must not attempt public registration."
            )
            assert not page_errors, f"Browser raised uncaught JavaScript errors: {page_errors}"
            assert dialogs, "Upload and restore confirmations should be shown before overwriting data."
            print("Cloud-sync UI passed: login, first upload, stale-revision warning, restore, and local-data retention after sign-out.")
            print(f"Observed mocked API calls: {len(api.requests)}; confirmation dialogs: {len(dialogs)}")
            browser.close()
            browser = None
    finally:
        if browser is not None:
            browser.close()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
