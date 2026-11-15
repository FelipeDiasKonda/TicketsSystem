"""Exercise ticket details in Chrome using an isolated SQLite API, never live data."""

import os
from functools import partial
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlsplit

from browser_status_smoke import BACKEND, PASSWORD, QuietHandler
from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.database import Base, get_db
from app.main import create_app
from app.services.seed import seed_demo_data


def main():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_demo_data(db, PASSWORD)
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(QuietHandler, directory=str(BACKEND.parent / "frontend/dist"))
    )
    Thread(target=server.serve_forever, daemon=True).start()
    origin = f"http://localhost:{server.server_address[1]}"
    get_settings().cors_origins = [origin]
    app = create_app()

    def database():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    try:
        with TestClient(app) as api, sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                executable_path=os.environ.get(
                    "BROWSER_EXECUTABLE", r"C:\Program Files\Google\Chrome\Application\chrome.exe"
                ),
            )
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            errors = []

            def route(route):
                request = route.request
                if urlsplit(request.url).path.startswith("/api/"):
                    api.cookies.clear()
                    response = api.request(
                        request.method,
                        "/api/" + request.url.split("/api/", 1)[1],
                        headers={
                            key: value
                            for key, value in request.headers.items()
                            if key not in ("host", "content-length")
                        },
                        content=request.post_data_buffer,
                    )
                    route.fulfill(
                        status=response.status_code,
                        headers=dict(response.headers),
                        body=response.content,
                    )
                elif request.url.startswith(origin + "/"):
                    route.continue_()
                else:
                    route.abort()

            context.route("**/*", route)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(origin)

            def login(email):
                page.get_by_label("E-mail", exact=True).fill(email)
                page.get_by_label("Senha", exact=True).fill(PASSWORD)
                page.get_by_role("button", name="Entrar", exact=True).click()
                expect(page.locator("tbody tr")).to_have_count(
                    3 if email.startswith("suporte") else 1
                )

            login("suporte1@gmail.com")
            opener = page.locator(".ticket-open").first
            opener.focus()
            page.keyboard.press("Enter")
            modal = page.get_by_role("dialog")
            expect(modal).to_be_visible()
            expect(modal.get_by_text("Solicitante", exact=True)).to_be_visible()
            expect(modal.locator(".detail-fields")).to_contain_text("Funcionário 3")
            trigger = modal.locator(".assignee-trigger")
            trigger.focus()
            page.keyboard.press("Enter")
            expect(modal.get_by_role("menu")).to_be_visible()
            page.keyboard.press("Escape")
            expect(modal.get_by_role("menu")).to_have_count(0)
            expect(modal).to_be_visible()
            expect(trigger).to_be_focused()
            page.keyboard.press("ArrowDown")
            expect(modal.get_by_role("menuitem", name="Atribuir a mim")).to_be_focused()
            page.keyboard.press("Enter")
            expect(
                modal.get_by_role("status").filter(has_text="Responsável atualizado")
            ).to_be_visible()
            expect(modal.locator(".assignee-trigger")).to_contain_text("Suporte 1")
            expect(modal.get_by_role("menu")).to_have_count(0)
            modal.get_by_label("Adicionar comentário").fill(
                "<script>alert('xss')</script>\nComentário de teste"
            )
            modal.get_by_role("button", name="Enviar comentário", exact=True).click()
            expect(modal.locator(".activity-list")).to_contain_text("<script>alert('xss')</script>")
            modal.get_by_role("tab", name="Histórico", exact=True).click()
            expect(modal.locator(".activity-list")).to_contain_text("Responsável: Não atribuído")
            expect(modal.locator(".activity-list")).to_contain_text("Criou o ticket")
            # Roving tab keyboard and native dialog focus trap.
            modal.get_by_role("tab", name="Histórico", exact=True).focus()
            page.keyboard.press("ArrowLeft")
            expect(modal.get_by_role("tab", name="Comentários", exact=True)).to_be_focused()
            page.keyboard.press("Escape")
            expect(modal).to_have_count(0)
            expect(page.locator('.view-switch button[aria-pressed="true"]')).to_be_focused()
            page.get_by_role("button", name="Quadro", exact=True).click()
            card = page.locator('[data-ticket-id="3"]')
            expect(card).to_be_visible()
            card.drag_to(page.locator('[data-status="in_progress"]'))
            expect(page.locator('[data-status="in_progress"] [data-ticket-id="3"]')).to_be_visible()
            expect(page.get_by_role("dialog")).to_have_count(0)
            page.locator('[data-ticket-id="3"] .ticket-open').click()
            modal = page.get_by_role("dialog")
            expect(modal).to_be_visible()
            modal.get_by_role("tab", name="Histórico", exact=True).click()
            expect(modal.locator(".activity-list")).to_contain_text("Aberto → Em andamento")
            modal.locator(".assignee-trigger").click()
            modal.get_by_role("menuitemradio", name="Suporte 2", exact=True).click()
            expect(
                modal.get_by_role("status").filter(has_text="Responsável atualizado")
            ).to_be_visible()
            expect(modal.locator(".assignee-trigger")).to_contain_text("Suporte 2")
            modal.locator(".assignee-trigger").click()
            modal.get_by_role("menuitem", name="Remover atribuição", exact=True).click()
            expect(modal.locator(".assignee-trigger")).to_contain_text("Não atribuído")
            page.keyboard.press("Escape")
            page.get_by_role("button", name="Sair da conta", exact=True).click()
            login("funcionario3@gmail.com")
            page.locator(".ticket-open").first.click()
            modal = page.get_by_role("dialog")
            expect(modal.get_by_label("Adicionar comentário")).to_be_visible()
            expect(modal.locator(".assignee-trigger")).to_have_count(0)
            expect(modal.locator(".status-select")).to_have_count(0)
            expect(modal.locator(".activity-list")).to_contain_text("Comentário de teste")
            page.set_viewport_size({"width": 390, "height": 844})
            expect(modal.get_by_role("button", name="Fechar detalhes")).to_be_visible()
            assert modal.evaluate("element => element.scrollWidth <= element.clientWidth")
            page.screenshot(path=str(BACKEND / ".pytest_cache/details-mobile.png"), full_page=True)
            modal.get_by_role("button", name="Fechar detalhes").click()
            expect(page.locator(".ticket-open").first).to_be_focused()
            assert errors == []
            browser.close()
        print(
            "Browser details smoke: modal, assignment, comments, history, "
            "drag, roles, focus, mobile OK"
        )
    finally:
        server.shutdown()
        server.server_close()
        engine.dispose()


if __name__ == "__main__":
    main()
