from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db.database import get_db
from app.main import app


def test_health_without_database():
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.0.0"}


def test_database_unavailable_does_not_expose_connection_details():
    class UnavailableSession:
        def execute(self, statement):
            raise OperationalError("SELECT 1", {}, Exception("private connection details"))

    app.dependency_overrides[get_db] = lambda: UnavailableSession()
    try:
        with TestClient(app) as client:
            response = client.get("/api/health/db")
        assert response.status_code == 503
        assert response.json() == {"detail": "Database unavailable"}
    finally:
        app.dependency_overrides.clear()


def test_database_health_when_available():
    class AvailableSession:
        def execute(self, statement):
            assert str(statement) == "SELECT 1"

    app.dependency_overrides[get_db] = lambda: AvailableSession()
    try:
        with TestClient(app) as client:
            response = client.get("/api/health/db")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "mysql"}
    finally:
        app.dependency_overrides.clear()


def test_openapi_preserves_health_routes():
    with TestClient(app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert set(paths) == {"/api/health", "/api/health/db"}
    for path in paths.values():
        assert path["get"]["tags"] == ["health"]
