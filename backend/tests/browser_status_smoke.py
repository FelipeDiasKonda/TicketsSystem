"""Optional browser integration test. Build frontend first; no live API/database is used."""

import os
import re
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

from environment import configure_test_environment

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
configure_test_environment()

from fastapi.testclient import TestClient  # noqa: E402
from playwright.sync_api import expect, sync_playwright  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.database import Base, get_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import User  # noqa: E402
from app.schemas.ticket import TicketCreate, TicketStatusUpdate  # noqa: E402
from app.services.seed import seed_demo_data  # noqa: E402
from app.services.ticket import create_ticket, update_ticket_status  # noqa: E402

PASSWORD = "browser-fixture-password"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def main():
    dist = BACKEND.parent / "frontend/dist"
    if not (dist / "index.html").exists():
        raise RuntimeError("Run npm run build in frontend first.")
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_demo_data(db, PASSWORD)
        employee = db.scalar(select(User).where(User.email == "funcionario1@gmail.com"))
        support = db.scalar(select(User).where(User.email == "suporte1@gmail.com"))
        for index in range(24):
            create_ticket(
                db,
                employee,
                TicketCreate(
                    title=f"Board pagination example {index}",
                    description="Browser fixture ticket.",
                    category="it",
                    priority="medium",
                ),
            )
        for steps in (1, 2, 3):
            ticket = create_ticket(
                db,
                employee,
                TicketCreate(
                    title=f"Workflow fixture {steps}",
                    description="Browser workflow fixture ticket.",
                    category="it",
                    priority="high",
                ),
            )
            for previous, following in list(
                {
                    "open": "in_progress",
                    "in_progress": "resolved",
                    "resolved": "closed",
                }.items()
            )[:steps]:
                update_ticket_status(
                    db,
                    ticket.id,
                    support,
                    TicketStatusUpdate(
                        expected_status=previous,
                        status=following,
                    ),
                )

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(dist)))
    Thread(target=server.serve_forever, daemon=True).start()
    origin = f"http://localhost:{server.server_address[1]}"
    get_settings().cors_origins = [origin]
    app = create_app()

    def database():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    patch_calls = []
    try:
        with TestClient(app) as api, sync_playwright() as playwright:
            browser_path = os.environ.get("BROWSER_EXECUTABLE")
            if not browser_path and sys.platform == "win32":
                browser_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            browser = playwright.chromium.launch(executable_path=browser_path, headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 1000})

            def route_api(route):
                # Intercept all API traffic, including OPTIONS; never contact live data.
                request = route.request
                headers = {
                    k: v for k, v in request.headers.items() if k not in ("host", "content-length")
                }
                api.cookies.clear()
                response = api.request(
                    request.method,
                    "/api/" + request.url.split("/api/", 1)[1],
                    headers=headers,
                    content=request.post_data_buffer,
                )
                if request.method == "PATCH":
                    patch_calls.append(response.status_code)
                route.fulfill(
                    status=response.status_code,
                    headers=dict(response.headers),
                    body=response.content,
                )

            def isolated_route(route):
                if urlsplit(route.request.url).path.startswith("/api/"):
                    route_api(route)
                elif route.request.url.startswith(origin + "/"):
                    route.continue_()
                else:
                    route.abort()

            context.route("**/*", isolated_route)
            page = context.new_page()
            page.goto(origin)

            def login_as(email):
                page.get_by_label("E-mail", exact=True).fill(email)
                page.get_by_label("Senha", exact=True).fill(PASSWORD)
                page.get_by_role("button", name="Entrar", exact=True).click()
                expect(page.get_by_role("button", name="Quadro", exact=True)).to_be_visible()

            login_as("suporte1@gmail.com")
            status = page.get_by_label("Alterar status do ticket #27", exact=True)
            expect(status.locator("option")).to_have_count(2)
            status.select_option("in_progress")
            expect(
                page.get_by_role("status").filter(has_text="Ticket #27 atualizado")
            ).to_be_visible()
            page.get_by_role("button", name="Quadro", exact=True).click()
            opened = page.locator('[data-status="open"]')
            progress = page.locator('[data-status="in_progress"]')
            resolved = page.locator('[data-status="resolved"]')
            closed = page.locator('[data-status="closed"]')
            expect(opened.locator(".ticket-card")).to_have_count(20)
            opened.get_by_role("button", name=re.compile("Carregar mais")).click()
            expect(opened.locator(".ticket-card")).to_have_count(26)
            before = len(patch_calls)
            opened.locator('[data-ticket-id="26"]').drag_to(closed)
            expect(opened.locator('[data-ticket-id="26"]')).to_be_visible()
            assert len(patch_calls) == before
            opened.locator('[data-ticket-id="26"]').drag_to(progress)
            expect(progress.locator('[data-ticket-id="26"]')).to_be_visible()
            button = progress.get_by_role(
                "button", name="Mover ticket #26 para Resolvido", exact=True
            )
            button.focus()
            page.keyboard.press("Enter")
            expect(resolved.locator('[data-ticket-id="26"]')).to_be_visible()
            screenshots = BACKEND / ".pytest_cache"
            screenshots.mkdir(exist_ok=True)
            page.screenshot(path=str(screenshots / "status-board-desktop.png"), full_page=True)

            # Another support user advances a loaded card; stale UI must show conflict and reload.
            cookie = next(item for item in context.cookies() if item["name"] == "tickets_session")
            api.cookies.clear()
            assert (
                api.patch(
                    "/api/tickets/25/status",
                    headers={
                        "X-CSRF-Protection": "1",
                        "Cookie": f"tickets_session={cookie['value']}",
                    },
                    json={"expected_status": "open", "status": "in_progress"},
                ).status_code
                == 200
            )
            opened.locator('[data-ticket-id="25"]').drag_to(progress)
            expect(page.get_by_role("alert").filter(has_text="status has changed")).to_be_visible()
            expect(progress.locator('[data-ticket-id="25"]')).to_be_visible()
            assert patch_calls[-1] == 409
            page.locator("#filter-category").select_option("hr")
            expect(opened.locator(".ticket-card")).to_have_count(1)
            page.get_by_role("button", name="Lista", exact=True).click()
            expect(page.locator("tbody tr")).to_have_count(1)
            expect(page.locator("#filter-category")).to_have_value("hr")
            page.get_by_role("button", name="Sair da conta", exact=True).click()
            login_as("funcionario1@gmail.com")
            expect(page.locator(".status-select")).to_have_count(0)
            page.get_by_role("button", name="Quadro", exact=True).click()
            expect(page.locator(".ticket-card").first).to_be_visible()
            expect(page.locator('.ticket-card[draggable="true"]')).to_have_count(0)
            expect(page.locator(".card-move")).to_have_count(0)
            page.set_viewport_size({"width": 390, "height": 844})
            expect(page.get_by_role("button", name="Lista", exact=True)).to_be_visible()
            screenshots = BACKEND / ".pytest_cache"
            screenshots.mkdir(exist_ok=True)
            page.screenshot(path=str(screenshots / "status-board-mobile.png"), full_page=True)
            browser.close()
        print(
            "Browser status smoke: list, drag/drop, keyboard, pagination, "
            "conflicts, filters and roles OK"
        )
    finally:
        server.shutdown()
        server.server_close()
        engine.dispose()


if __name__ == "__main__":
    main()
