import io

import mysql.connector
import pytest

from app import app


class FakeCursor:
    def __init__(self, results=None, fail_on=None, single_results=None):
        self.results = list(results or [])
        self.single_results = list(single_results or [])
        self.fail_on = fail_on
        self.calls = []
        self.lastrowid = 42
        self.rowcount = 1
        self.closed = False

    def execute(self, query, params=None):
        self.calls.append((query, params))
        if self.fail_on and self.fail_on in query:
            raise mysql.connector.IntegrityError("Constraint rejected the write")

    def fetchall(self):
        return self.results.pop(0) if self.results else []

    def fetchone(self):
        return self.single_results.pop(0) if self.single_results else (42,)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self, dictionary=False):
        return self.fake_cursor

    def start_transaction(self):
        pass

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def is_connected(self):
        return not self.closed

    def close(self):
        self.closed = True


@pytest.fixture
def client(monkeypatch):
    app.config["TESTING"] = True
    monkeypatch.setattr("app.get_user_permissions", lambda _user_id: {
        "registry.read", "audit.read", "agents.manage", "resources.manage",
        "dependencies.manage", "resources.health", "imports.manage", "users.manage",
    })
    with app.test_client() as test_client:
        with test_client.session_transaction() as browser_session:
            browser_session["user_id"] = 7
            browser_session["csrf_token"] = "test-csrf-token"
        test_client.environ_base["HTTP_X_CSRF_TOKEN"] = "test-csrf-token"
        yield test_client


def test_protected_api_requires_login():
    app.config["TESTING"] = True
    with app.test_client() as unauthenticated_client:
        response = unauthenticated_client.get("/api/overview")
    assert response.status_code == 401


def test_protected_api_checks_database_permissions(monkeypatch):
    app.config["TESTING"] = True
    monkeypatch.setattr("app.get_user_permissions", lambda _user_id: {"registry.read"})
    with app.test_client() as restricted_client:
        with restricted_client.session_transaction() as browser_session:
            browser_session["user_id"] = 7
            browser_session["csrf_token"] = "test-csrf-token"
        response = restricted_client.post(
            "/api/agents",
            json={"name": "No Permission", "purpose": "test", "team_id": 1},
            headers={"X-CSRF-Token": "test-csrf-token"},
        )
    assert response.status_code == 403


def test_cookie_authenticated_mutation_requires_csrf_token(monkeypatch):
    app.config["TESTING"] = True
    monkeypatch.setattr("app.get_user_permissions", lambda _user_id: {"agents.manage"})
    with app.test_client() as browser:
        with browser.session_transaction() as browser_session:
            browser_session["user_id"] = 7
            browser_session["csrf_token"] = "expected-token"
        response = browser.post("/api/agents", json={
            "name": "CSRF test",
            "purpose": "No token should block this",
            "team_id": 1,
        })
    assert response.status_code == 403
    assert "CSRF" in response.get_json()["error"]


def test_overview_returns_all_registry_collections(monkeypatch, client):
    cursor = FakeCursor(results=[[], [], [], [], [], []])
    connection = FakeConnection(cursor)
    monkeypatch.setattr("app.get_db_connection", lambda: connection)

    response = client.get("/api/overview")

    assert response.status_code == 200
    assert response.get_json() == {
        "agents": [], "resources": [], "workflows": [],
        "dependencies": [], "teams": [], "companies": [],
    }
    assert len(cursor.calls) == 6
    assert connection.closed


def test_overview_allows_vite_fallback_port(monkeypatch, client):
    cursor = FakeCursor(results=[[], [], [], [], [], []])
    connection = FakeConnection(cursor)
    monkeypatch.setattr("app.get_db_connection", lambda: connection)

    response = client.get(
        "/api/overview",
        headers={"Origin": "http://127.0.0.1:5174"},
    )

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "http://127.0.0.1:5174"


def test_update_agent_saves_manual_edits(monkeypatch, client):
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    monkeypatch.setattr("app.get_db_connection", lambda: connection)

    response = client.put("/api/agents/9", json={
        "name": "Edited Agent",
        "purpose": "Updated purpose",
        "team_id": 2,
    })

    assert response.status_code == 200
    assert any("UPDATE agents" in query for query, _ in cursor.calls)
    assert connection.commits == 1


def test_create_resource_saves_manual_resource(monkeypatch, client):
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    monkeypatch.setattr("app.get_db_connection", lambda: connection)

    response = client.post("/api/resources", json={
        "name": "New Company API",
        "resource_type": "API",
        "endpoint_url": "https://api.example.test",
    })

    assert response.status_code == 201
    assert response.get_json()["resource_id"] == 42
    assert any("INSERT INTO resources" in query for query, _ in cursor.calls)
    assert connection.commits == 1


def test_ingest_creates_teams_resources_agents_and_dependencies(monkeypatch, client):
    cursor = FakeCursor(single_results=[(1,), (11,), (21,), (77,)])
    connection = FakeConnection(cursor)
    monkeypatch.setattr("app.get_db_connection", lambda: connection)

    response = client.post("/api/ingest", data={
        "file": (
            io.BytesIO(
                b'{"company":{"name":"Example Studio Co"},'
                b'"teams":[{"name":"Example Studio"}],'
                b'"resources":[{"name":"Private Model","resource_type":"LLM",'
                b'"endpoint_url":"https://models.example.test"}],'
                b'"architecture":[{"agent":"Research Agent","purpose":"Finds evidence",'
                b'"team":"Example Studio","dependencies":["Private Model"]}]}'
            ),
            "company.json",
            "application/json",
        )
    }, content_type="multipart/form-data")

    assert response.status_code == 200
    company_result = response.get_json()["companies"][0]
    assert company_result["teams_processed"] == 1
    assert company_result["resources_processed"] == 1
    assert company_result["agents_processed"] == 1
    assert any("DELETE FROM agents WHERE company_id" in query for query, _ in cursor.calls)
    assert any("DELETE FROM resources WHERE company_id" in query for query, _ in cursor.calls)
    assert all("company_id = %s" in query for query, _ in cursor.calls if query.startswith("DELETE FROM"))
    assert any("INSERT INTO teams" in query for query, _ in cursor.calls)
    assert any("INSERT INTO resources" in query for query, _ in cursor.calls)
    assert any("INSERT INTO agents" in query for query, _ in cursor.calls)
    dependency_insert = next(
        (params for query, params in cursor.calls if "INSERT INTO agent_resources" in query),
        None,
    )
    assert dependency_insert == (42, 21, "RUNTIME", True)
    assert connection.commits == 1
    assert connection.rollbacks == 0


def test_ingest_rolls_back_when_resource_type_is_invalid(monkeypatch, client):
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    monkeypatch.setattr("app.get_db_connection", lambda: connection)

    response = client.post("/api/ingest", data={
        "file": (
            io.BytesIO(
                b'{"company":"Example Studio Co","architecture":[{"agent":"Research Agent","team":"Example Studio",'
                b'"dependencies":[{"name":"Unknown Class","resource_type":"ALIEN"}]}]}'
            ),
            "company.json",
            "application/json",
        )
    }, content_type="multipart/form-data")

    assert response.status_code == 400
    assert "invalid resource_type" in response.get_json()["error"]
    assert connection.commits == 0
    assert connection.rollbacks == 1


def test_ingest_creates_workflow_steps_for_imported_agents(monkeypatch, client):
    cursor = FakeCursor(single_results=[(1,), (42,)])
    connection = FakeConnection(cursor)
    monkeypatch.setattr("app.get_db_connection", lambda: connection)

    response = client.post("/api/ingest", data={
        "file": (
            io.BytesIO(
                b'{"company":"Pipeline Inc","architecture":[{"agent":"Pipeline Agent","team":"Pipeline Team"}],'
                b'"workflows":[{"name":"Pipeline","team":"Pipeline Team",'
                b'"agents":["Pipeline Agent"]}]}'
            ),
            "company.json",
            "application/json",
        )
    }, content_type="multipart/form-data")

    assert response.status_code == 200
    assert response.get_json()["companies"][0]["workflows_processed"] == 1
    assert any("INSERT INTO workflows" in query for query, _ in cursor.calls)
    assert any("INSERT INTO workflow_agents" in query for query, _ in cursor.calls)
    assert connection.commits == 1


def test_ingest_replaces_multiple_distinct_companies_atomically(monkeypatch, client):
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    monkeypatch.setattr("app.get_db_connection", lambda: connection)

    company_files = [
        (io.BytesIO(b'{"company":"Company One","architecture":[]}'), "one.json", "application/json"),
        (io.BytesIO(b'{"company":"Company Two","architecture":[]}'), "two.json", "application/json"),
    ]
    response = client.post("/api/ingest", data={"files": company_files}, content_type="multipart/form-data")

    assert response.status_code == 200
    assert len(response.get_json()["companies"]) == 2
    company_deletes = [params for query, params in cursor.calls if "DELETE FROM agents WHERE company_id" in query]
    assert company_deletes == [(42,), (42,)]
    assert connection.commits == 1
    assert connection.rollbacks == 0


def test_ingest_rejects_duplicate_company_files_without_database_writes(monkeypatch, client):
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    monkeypatch.setattr("app.get_db_connection", lambda: connection)

    company_files = [
        (io.BytesIO(b'{"company":"Duplicate Co","architecture":[]}'), "one.json", "application/json"),
        (io.BytesIO(b'{"company":"duplicate co","architecture":[]}'), "two.json", "application/json"),
    ]
    response = client.post("/api/ingest", data={"files": company_files}, content_type="multipart/form-data")

    assert response.status_code == 400
    assert "one JSON file per company" in response.get_json()["error"]
    assert connection.commits == 0
    assert connection.rollbacks == 0
