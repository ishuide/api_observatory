import json
import os
import secrets
from datetime import timedelta
from functools import wraps

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import mysql.connector
from flask import Flask, g, jsonify, request, session
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ORIGINS",
        ",".join(
            f"{host}:{port}"
            for host in ("http://127.0.0.1", "http://localhost")
            for port in range(5173, 5181)
        ),
    ).split(",")
    if origin.strip()
]
CORS(app, resources={r"/api/*": {"origins": CORS_ORIGINS}}, supports_credentials=True)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "0") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "127.0.0.1"),
    "port": int(os.environ.get("DB_PORT", "3307")),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "ai_agent_registry"),
}

RESOURCE_TYPES = {"LLM", "API", "VECTOR_DB", "MEMORY", "TOOL"}


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


def close_db(cursor, connection):
    if cursor is not None:
        cursor.close()
    if connection is not None and connection.is_connected():
        connection.close()


def error_response(error, status=400):
    return jsonify({"error": str(error)}), status


def require_permission(permission):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user_id = session.get("user_id")
            if user_id is None:
                return error_response("Authentication required", 401)
            try:
                permissions = get_user_permissions(user_id)
                if permission not in permissions:
                    return error_response("Permission denied", 403)
                g.permissions = permissions
            except mysql.connector.Error as error:
                app.logger.exception("Could not verify application permissions")
                return error_response("Permission service unavailable", 503)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def get_user_permissions(user_id):
    connection = cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            SELECT p.permission_key
            FROM app_user_roles AS ur
            JOIN app_role_permissions AS rp ON rp.role_id = ur.role_id
            JOIN app_permissions AS p ON p.permission_id = rp.permission_id
            JOIN app_users AS u ON u.user_id = ur.user_id
            WHERE ur.user_id = %s AND u.is_active = TRUE
        """, (user_id,))
        return {row[0] for row in cursor.fetchall()}
    finally:
        close_db(cursor, connection)


def current_user_data(user_id):
    connection = cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT u.user_id, u.username, r.role_name
            FROM app_users AS u
            JOIN app_user_roles AS ur ON ur.user_id = u.user_id
            JOIN app_roles AS r ON r.role_id = ur.role_id
            WHERE u.user_id = %s AND u.is_active = TRUE
            ORDER BY r.role_name
        """, (user_id,))
        rows = cursor.fetchall()
        if not rows:
            return None
        permissions = sorted(get_user_permissions(user_id))
        return {
            "user_id": rows[0]["user_id"],
            "username": rows[0]["username"],
            "roles": sorted({row["role_name"] for row in rows}),
            "permissions": permissions,
            "csrf_token": session.get("csrf_token"),
        }
    finally:
        close_db(cursor, connection)


@app.before_request
def protect_cookie_authenticated_writes():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    if request.path == "/api/auth/login" or not request.path.startswith("/api/"):
        return None
    if session.get("user_id") is None:
        return None
    expected = session.get("csrf_token")
    supplied = request.headers.get("X-CSRF-Token")
    if not expected or not secrets.compare_digest(expected, supplied or ""):
        return error_response("CSRF token missing or invalid", 403)
    return None


@app.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return error_response("Username and password are required", 400)
    connection = cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT user_id, password_hash
            FROM app_users
            WHERE username = %s AND is_active = TRUE
        """, (username,))
        user = cursor.fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            return error_response("Invalid username or password", 401)
        cursor.execute("UPDATE app_users SET last_login_at = CURRENT_TIMESTAMP WHERE user_id = %s",
                       (user["user_id"],))
        connection.commit()
        session.clear()
        session.permanent = True
        session["user_id"] = user["user_id"]
        session["csrf_token"] = secrets.token_urlsafe(32)
        return jsonify(current_user_data(user["user_id"]))
    except mysql.connector.Error as error:
        if connection:
            connection.rollback()
        app.logger.exception("Login failed due to a database error")
        return error_response("Authentication service unavailable", 503)
    finally:
        close_db(cursor, connection)


@app.get("/api/auth/me")
def get_session_user():
    user_id = session.get("user_id")
    if user_id is None:
        return error_response("Authentication required", 401)
    try:
        user = current_user_data(user_id)
        if user is None:
            session.clear()
            return error_response("Authentication required", 401)
        return jsonify(user)
    except mysql.connector.Error:
        app.logger.exception("Could not load authenticated user")
        return error_response("Authentication service unavailable", 503)


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})


def upsert_company(cursor, company):
    if isinstance(company, str):
        company = {"name": company}
    if not isinstance(company, dict) or not isinstance(company.get("name"), str) or not company["name"].strip():
        raise ValueError("Each JSON file must declare company.name")
    company_name = company["name"].strip()
    cursor.execute("""
        INSERT INTO companies (name) VALUES (%s)
        ON DUPLICATE KEY UPDATE company_id = LAST_INSERT_ID(company_id)
    """, (company_name,))
    cursor.execute("SELECT company_id FROM companies WHERE name = %s", (company_name,))
    result = cursor.fetchone()
    if result is None:
        raise ValueError(f"Could not resolve company '{company_name}'")
    return result[0]


def get_legacy_company_id(cursor):
    return upsert_company(cursor, "Legacy Registry")


def upsert_team(cursor, company_id, team):
    if isinstance(team, str):
        team = {"name": team}
    if not isinstance(team, dict) or not isinstance(team.get("name"), str) or not team["name"].strip():
        raise ValueError("Each team must have a non-empty name")
    cursor.execute("""
        INSERT INTO teams (company_id, name, lead_email)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            lead_email = COALESCE(VALUES(lead_email), lead_email)
    """, (company_id, team["name"].strip(), team.get("lead_email")))
    cursor.execute("SELECT team_id FROM teams WHERE company_id = %s AND name = %s",
                   (company_id, team["name"].strip()))
    result = cursor.fetchone()
    if result is None:
        raise ValueError(f"Could not resolve saved team '{team['name'].strip()}'")
    return result[0]


def upsert_resource(cursor, company_id, resource):
    if isinstance(resource, str):
        resource = {"name": resource, "resource_type": "TOOL"}
    if not isinstance(resource, dict) or not isinstance(resource.get("name"), str) or not resource["name"].strip():
        raise ValueError("Each resource must have a non-empty name")
    name = resource["name"].strip()
    resource_type = str(resource.get("resource_type", "TOOL")).upper()
    if resource_type not in RESOURCE_TYPES:
        raise ValueError(
            f"Resource '{name}' has invalid resource_type '{resource_type}'. "
            f"Use one of: {', '.join(sorted(RESOURCE_TYPES))}"
        )
    status = str(resource.get("status", "HEALTHY")).upper()
    if status not in {"HEALTHY", "DEGRADED", "OFFLINE"}:
        raise ValueError(f"Resource '{name}' has invalid status '{status}'")
    cursor.execute("""
        INSERT INTO resources (company_id, name, resource_type, endpoint_url, status)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            resource_type = VALUES(resource_type),
            endpoint_url = COALESCE(VALUES(endpoint_url), endpoint_url),
            status = VALUES(status)
    """, (company_id, name, resource_type, resource.get("endpoint_url"), status))
    cursor.execute("SELECT resource_id FROM resources WHERE company_id = %s AND name = %s",
                   (company_id, name))
    result = cursor.fetchone()
    if result is None:
        raise ValueError(f"Could not resolve saved resource '{name}'")
    return result[0]


@app.get("/api/overview")
@require_permission("registry.read")
def get_overview():
    connection = cursor = None
    try:
        company_id = request.args.get("company_id", type=int)
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        agent_company_clause = "WHERE a.company_id = %s" if company_id else ""
        cursor.execute(f"""
                 SELECT a.agent_id, a.company_id, c.name AS company_name, a.name, a.purpose, a.status, t.name AS team_name,
                   COUNT(ar.resource_id) AS resource_count
            FROM agents AS a
            JOIN teams AS t ON t.team_id = a.team_id
                 JOIN companies AS c ON c.company_id = a.company_id
            LEFT JOIN agent_resources AS ar ON ar.agent_id = a.agent_id
            {agent_company_clause}
            GROUP BY a.agent_id, a.company_id, c.name, a.name, a.purpose, a.status, t.name
            ORDER BY a.agent_id
        """, (company_id,) if company_id else None)
        agents = cursor.fetchall()
        resource_company_clause = "WHERE r.company_id = %s" if company_id else ""
        cursor.execute(f"""
            SELECT r.*, c.name AS company_name
            FROM resources AS r
            JOIN companies AS c ON c.company_id = r.company_id
            {resource_company_clause}
            ORDER BY r.resource_id
        """, (company_id,) if company_id else None)
        resources = cursor.fetchall()
        workflow_company_clause = "WHERE w.company_id = %s" if company_id else ""
        cursor.execute(f"""
                 SELECT w.workflow_id, w.company_id, c.name AS company_name,
                     w.name, w.criticality_level, t.name AS team_name,
                   COUNT(wa.agent_id) AS agent_count
            FROM workflows AS w
            JOIN teams AS t ON t.team_id = w.team_id
                 JOIN companies AS c ON c.company_id = w.company_id
            LEFT JOIN workflow_agents AS wa ON wa.workflow_id = w.workflow_id
            {workflow_company_clause}
            GROUP BY w.workflow_id, w.company_id, c.name, w.name, w.criticality_level, t.name
            ORDER BY w.workflow_id
        """, (company_id,) if company_id else None)
        workflows = cursor.fetchall()
        dependency_company_clause = "WHERE a.company_id = %s" if company_id else ""
        cursor.execute(f"""
            SELECT ar.agent_id, ar.resource_id, a.name AS agent_name,
                   r.name AS resource_name, r.resource_type, ar.dependency_type,
                     ar.is_critical, r.status AS resource_status, c.name AS company_name
            FROM agent_resources AS ar
            JOIN agents AS a ON a.agent_id = ar.agent_id
            JOIN resources AS r ON r.resource_id = ar.resource_id
                 JOIN companies AS c ON c.company_id = a.company_id
            {dependency_company_clause}
            ORDER BY a.name, r.name
        """, (company_id,) if company_id else None)
        dependencies = cursor.fetchall()
        team_company_clause = "WHERE t.company_id = %s" if company_id else ""
        cursor.execute(f"""
            SELECT t.team_id, t.company_id, t.name, c.name AS company_name
            FROM teams AS t
            JOIN companies AS c ON c.company_id = t.company_id
            {team_company_clause}
            ORDER BY c.name, t.name
        """, (company_id,) if company_id else None)
        teams = cursor.fetchall()
        cursor.execute("SELECT company_id, name FROM companies ORDER BY name")
        companies = cursor.fetchall()
        return jsonify({
            "agents": agents,
            "resources": resources,
            "workflows": workflows,
            "dependencies": dependencies,
            "teams": teams,
            "companies": companies,
        })
    except mysql.connector.Error as error:
        app.logger.exception("Failed to load registry overview")
        return error_response(error, 503)
    finally:
        close_db(cursor, connection)


@app.post("/api/agents")
@require_permission("agents.manage")
def add_agent():
    data = request.get_json(silent=True) or {}
    required = ("name", "purpose", "team_id")
    if any(not data.get(field) for field in required):
        return error_response("name, purpose, and team_id are required")
    connection = cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO agents (company_id, name, purpose, team_id)
            SELECT company_id, %s, %s, team_id
            FROM teams WHERE team_id = %s
        """, (data["name"].strip(), data["purpose"].strip(), data["team_id"]))
        if cursor.rowcount == 0:
            return error_response("Selected team does not exist", 400)
        connection.commit()
        return jsonify({"message": "Agent registered successfully", "agent_id": cursor.lastrowid}), 201
    except mysql.connector.Error as error:
        if connection:
            connection.rollback()
        return error_response(error)
    finally:
        close_db(cursor, connection)


@app.put("/api/agents/<int:agent_id>")
@require_permission("agents.manage")
def update_agent(agent_id):
    data = request.get_json(silent=True) or {}
    required = ("name", "purpose", "team_id")
    if any(not data.get(field) for field in required):
        return error_response("name, purpose, and team_id are required")
    connection = cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE agents
            JOIN teams AS t ON t.team_id = %s
            SET agents.company_id = t.company_id,
                agents.name = %s,
                agents.purpose = %s,
                agents.team_id = t.team_id
            WHERE agents.agent_id = %s
        """, (data["team_id"], data["name"].strip(), data["purpose"].strip(), agent_id))
        if cursor.rowcount == 0:
            cursor.execute("SELECT agent_id FROM agents WHERE agent_id = %s", (agent_id,))
            if cursor.fetchone() is None:
                return error_response("Agent not found", 404)
        connection.commit()
        return jsonify({"message": "Agent updated"})
    except mysql.connector.Error as error:
        if connection:
            connection.rollback()
        return error_response(error)
    finally:
        close_db(cursor, connection)


@app.delete("/api/agents/<int:agent_id>")
@require_permission("agents.manage")
def delete_agent(agent_id):
    connection = cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("DELETE FROM agents WHERE agent_id = %s", (agent_id,))
        if cursor.rowcount == 0:
            return error_response("Agent not found", 404)
        connection.commit()
        return jsonify({"message": "Agent deleted"})
    except mysql.connector.Error as error:
        if connection:
            connection.rollback()
        return error_response(error)
    finally:
        close_db(cursor, connection)


@app.post("/api/resources")
@require_permission("resources.manage")
def add_resource():
    data = request.get_json(silent=True) or {}
    connection = cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        company_id = data.get("company_id") or get_legacy_company_id(cursor)
        resource_id = upsert_resource(cursor, company_id, data)
        connection.commit()
        return jsonify({"message": "Resource saved", "resource_id": resource_id}), 201
    except (mysql.connector.Error, TypeError, ValueError) as error:
        if connection:
            connection.rollback()
        return error_response(error)
    finally:
        close_db(cursor, connection)


@app.put("/api/resources/<int:resource_id>")
@require_permission("resources.manage")
def update_resource(resource_id):
    data = request.get_json(silent=True) or {}
    required = ("name", "resource_type", "status")
    if any(not data.get(field) for field in required):
        return error_response("name, resource_type, and status are required")
    try:
        name = data["name"].strip()
        resource_type = str(data["resource_type"]).upper()
        status = str(data["status"]).upper()
        if not name:
            return error_response("name is required")
        if resource_type not in RESOURCE_TYPES:
            return error_response(f"Invalid resource_type: {resource_type}")
        if status not in {"HEALTHY", "DEGRADED", "OFFLINE"}:
            return error_response(f"Invalid resource status: {status}")
    except (AttributeError, TypeError) as error:
        return error_response(error)
    connection = cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT status FROM resources WHERE resource_id = %s FOR UPDATE", (resource_id,))
        existing_resource = cursor.fetchone()
        if existing_resource is None:
            return error_response("Resource not found", 404)
        old_status = existing_resource[0]
        if old_status != status and status == "OFFLINE":
            cursor.execute(
                "CALL deactivate_resource_and_cascade(%s, %s)",
                (resource_id, "Resource status updated from registry UI"),
            )
        elif old_status == "OFFLINE" and status == "HEALTHY":
            cursor.execute("CALL recover_resource(%s)", (resource_id,))
        cursor.execute("""
            UPDATE resources
            SET name = %s, resource_type = %s, endpoint_url = %s
            WHERE resource_id = %s
        """, (name, resource_type, data.get("endpoint_url"), resource_id))
        if old_status != status and status == "DEGRADED":
            cursor.execute("UPDATE resources SET status = 'DEGRADED' WHERE resource_id = %s", (resource_id,))
        elif old_status == "DEGRADED" and status == "HEALTHY":
            cursor.execute("UPDATE resources SET status = 'HEALTHY' WHERE resource_id = %s", (resource_id,))
        connection.commit()
        return jsonify({"message": "Resource updated"})
    except mysql.connector.Error as error:
        if connection:
            connection.rollback()
        return error_response(error)
    finally:
        close_db(cursor, connection)


@app.delete("/api/resources/<int:resource_id>")
@require_permission("resources.manage")
def delete_resource(resource_id):
    connection = cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("DELETE FROM resources WHERE resource_id = %s", (resource_id,))
        if cursor.rowcount == 0:
            return error_response("Resource not found", 404)
        connection.commit()
        return jsonify({"message": "Resource deleted"})
    except mysql.connector.Error as error:
        if connection:
            connection.rollback()
        return error_response(error)
    finally:
        close_db(cursor, connection)


@app.post("/api/dependencies")
@require_permission("dependencies.manage")
def add_dependency():
    data = request.get_json(silent=True) or {}
    required = ("agent_id", "resource_id", "dependency_type")
    if any(field not in data for field in required):
        return error_response("agent_id, resource_id, and dependency_type are required")
    connection = cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO agent_resources (agent_id, resource_id, dependency_type, is_critical)
            SELECT a.agent_id, r.resource_id, %s, %s
            FROM agents AS a
            JOIN resources AS r ON r.resource_id = %s AND r.company_id = a.company_id
            WHERE a.agent_id = %s
        """, (data["dependency_type"], data.get("is_critical", True),
              data["resource_id"], data["agent_id"]))
        if cursor.rowcount == 0:
            return error_response("Agent and resource must exist in the same company")
        connection.commit()
        return jsonify({"message": "Dependency linked successfully"}), 201
    except mysql.connector.Error as error:
        if connection:
            connection.rollback()
        return error_response(error)
    finally:
        close_db(cursor, connection)


@app.delete("/api/dependencies/<int:agent_id>/<int:resource_id>")
@require_permission("dependencies.manage")
def delete_dependency(agent_id, resource_id):
    connection = cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM agent_resources WHERE agent_id = %s AND resource_id = %s",
            (agent_id, resource_id),
        )
        connection.commit()
        return jsonify({"message": "Dependency revoked"})
    except mysql.connector.Error as error:
        if connection:
            connection.rollback()
        return error_response(error)
    finally:
        close_db(cursor, connection)


@app.post("/api/resources/<int:resource_id>/deactivate")
@require_permission("resources.health")
def deactivate_resource(resource_id):
    connection = cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("CALL deactivate_resource_and_cascade(%s, %s)",
                       (resource_id, "Triggered from registry UI"))
        connection.commit()
        return jsonify({"message": f"Resource {resource_id} deactivated with critical dependents"})
    except mysql.connector.Error as error:
        if connection:
            connection.rollback()
        return error_response(error)
    finally:
        close_db(cursor, connection)


@app.post("/api/resources/<int:resource_id>/recover")
@require_permission("resources.health")
def recover_resource(resource_id):
    connection = cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("CALL recover_resource(%s)", (resource_id,))
        connection.commit()
        return jsonify({"message": f"Resource {resource_id} recovered"})
    except mysql.connector.Error as error:
        if connection:
            connection.rollback()
        return error_response(error)
    finally:
        close_db(cursor, connection)


@app.get("/api/impact/<int:resource_id>")
@require_permission("registry.read")
def impact_analysis(resource_id):
    connection = cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            WITH RECURSIVE blast_radius (agent_id, depth) AS (
                SELECT ar.agent_id, 1
                FROM agent_resources AS ar
                WHERE ar.resource_id = %s AND ar.is_critical = TRUE
                UNION DISTINCT
                SELECT next_agent.agent_id, br.depth + 1
                FROM blast_radius AS br
                JOIN workflow_agents AS current_step ON current_step.agent_id = br.agent_id
                JOIN workflow_agents AS next_step
                  ON next_step.workflow_id = current_step.workflow_id
                 AND next_step.execution_step > current_step.execution_step
                JOIN agents AS next_agent ON next_agent.agent_id = next_step.agent_id
                WHERE br.depth < 10
            )
            SELECT br.agent_id, a.name AS agent_name, MIN(br.depth) AS depth,
                   GROUP_CONCAT(DISTINCT w.name ORDER BY w.name SEPARATOR ', ') AS workflow_name,
                   MAX(CASE w.criticality_level
                       WHEN 'CRITICAL' THEN 4 WHEN 'HIGH' THEN 3
                       WHEN 'MEDIUM' THEN 2 ELSE 1 END) AS criticality_rank,
                   SUBSTRING_INDEX(GROUP_CONCAT(w.criticality_level ORDER BY
                       CASE w.criticality_level WHEN 'CRITICAL' THEN 4
                       WHEN 'HIGH' THEN 3 WHEN 'MEDIUM' THEN 2 ELSE 1 END DESC), ',', 1)
                       AS criticality_level
            FROM blast_radius AS br
            JOIN agents AS a ON a.agent_id = br.agent_id
            LEFT JOIN workflow_agents AS wa ON wa.agent_id = a.agent_id
            LEFT JOIN workflows AS w ON w.workflow_id = wa.workflow_id
            GROUP BY br.agent_id, a.name
            ORDER BY depth, a.name
        """, (resource_id,))
        results = cursor.fetchall()
        for row in results:
            row.pop("criticality_rank", None)
        return jsonify(results)
    except mysql.connector.Error as error:
        app.logger.exception("Failed to calculate resource impact")
        return error_response(error, 503)
    finally:
        close_db(cursor, connection)


@app.get("/api/audit")
@require_permission("audit.read")
def get_audit():
    connection = cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM audit_logs ORDER BY created_at DESC, log_id DESC LIMIT 50")
        return jsonify(cursor.fetchall())
    except mysql.connector.Error as error:
        return error_response(error, 503)
    finally:
        close_db(cursor, connection)


@app.get("/api/admin/users")
@require_permission("users.manage")
def list_users():
    connection = cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT u.user_id, u.username, u.is_active, u.created_at, u.last_login_at,
                   GROUP_CONCAT(r.role_name ORDER BY r.role_name SEPARATOR ',') AS roles
            FROM app_users AS u
            LEFT JOIN app_user_roles AS ur ON ur.user_id = u.user_id
            LEFT JOIN app_roles AS r ON r.role_id = ur.role_id
            GROUP BY u.user_id, u.username, u.is_active, u.created_at, u.last_login_at
            ORDER BY u.username
        """)
        return jsonify(cursor.fetchall())
    except mysql.connector.Error as error:
        return error_response(error, 503)
    finally:
        close_db(cursor, connection)


@app.post("/api/admin/users")
@require_permission("users.manage")
def create_user():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    role_name = data.get("role", "Viewer")
    if len(username) < 3 or len(username) > 80:
        return error_response("Username must be 3 to 80 characters")
    if len(password) < 12:
        return error_response("Password must be at least 12 characters")
    if role_name not in {"Admin", "Operator", "Viewer"}:
        return error_response("Role must be Admin, Operator, or Viewer")
    connection = cursor = None
    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor()
        cursor.execute("SELECT role_id FROM app_roles WHERE role_name = %s", (role_name,))
        role = cursor.fetchone()
        if role is None:
            return error_response("Configured role not found", 500)
        cursor.execute("""
            INSERT INTO app_users (username, password_hash)
            VALUES (%s, %s)
        """, (username, generate_password_hash(password)))
        user_id = cursor.lastrowid
        cursor.execute("INSERT INTO app_user_roles (user_id, role_id) VALUES (%s, %s)",
                       (user_id, role[0]))
        connection.commit()
        return jsonify({"message": "User created", "user_id": user_id}), 201
    except mysql.connector.Error as error:
        if connection:
            connection.rollback()
        return error_response(error)
    finally:
        close_db(cursor, connection)


@app.put("/api/admin/users/<int:user_id>")
@require_permission("users.manage")
def update_user(user_id):
    data = request.get_json(silent=True) or {}
    role_name = data.get("role")
    is_active = data.get("is_active")
    if role_name not in {"Admin", "Operator", "Viewer"}:
        return error_response("Role must be Admin, Operator, or Viewer")
    if not isinstance(is_active, bool):
        return error_response("is_active must be true or false")
    if user_id == session.get("user_id") and not is_active:
        return error_response("You cannot deactivate your own account")

    connection = cursor = None
    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor()
        cursor.execute("SELECT role_id FROM app_roles WHERE role_name = %s", (role_name,))
        role = cursor.fetchone()
        if role is None:
            return error_response("Configured role not found", 500)
        cursor.execute("UPDATE app_users SET is_active = %s WHERE user_id = %s", (is_active, user_id))
        if cursor.rowcount == 0:
            cursor.execute("SELECT user_id FROM app_users WHERE user_id = %s", (user_id,))
            if cursor.fetchone() is None:
                return error_response("User not found", 404)
        cursor.execute("DELETE FROM app_user_roles WHERE user_id = %s", (user_id,))
        cursor.execute("INSERT INTO app_user_roles (user_id, role_id) VALUES (%s, %s)",
                       (user_id, role[0]))
        connection.commit()
        return jsonify({"message": "User role and status updated"})
    except mysql.connector.Error as error:
        if connection:
            connection.rollback()
        return error_response(error)
    finally:
        close_db(cursor, connection)


def replace_company_payload(cursor, payload):
    if not isinstance(payload, dict):
        raise ValueError("The JSON root must be an object")
    company = payload.get("company")
    if isinstance(company, str):
        company = {"name": company}
    if not isinstance(company, dict) or not isinstance(company.get("name"), str) or not company["name"].strip():
        raise ValueError("Every import file must include company.name")
    company_name = company["name"].strip()
    company_id = upsert_company(cursor, {"name": company_name})

    architecture = payload.get("architecture", payload.get("agents"))
    teams = payload.get("teams", [])
    resources = payload.get("resources", [])
    workflows = payload.get("workflows", [])
    if not isinstance(architecture, list):
        raise ValueError("JSON must contain an 'architecture' or 'agents' array")
    if not all(isinstance(items, list) for items in (teams, resources, workflows)):
        raise ValueError("teams, resources, and workflows must be arrays when provided")

    # This is a full company snapshot replacement; other companies are untouched.
    cursor.execute("DELETE FROM agents WHERE company_id = %s", (company_id,))
    cursor.execute("DELETE FROM workflows WHERE company_id = %s", (company_id,))
    cursor.execute("DELETE FROM resources WHERE company_id = %s", (company_id,))
    cursor.execute("DELETE FROM teams WHERE company_id = %s", (company_id,))

    team_ids = {}
    resource_ids = {}
    workflow_ids = {}

    for team in teams:
        team_name = team.get("name") if isinstance(team, dict) else team
        if not isinstance(team_name, str) or not team_name.strip():
            raise ValueError("Each team must be a name or an object containing a name")
        team_name = team_name.strip()
        if team_name in team_ids:
            raise ValueError(f"Duplicate team name in company file: '{team_name}'")
        team_ids[team_name] = upsert_team(cursor, company_id, team)

    for resource in resources:
        resource_name = resource.get("name") if isinstance(resource, dict) else resource
        if not isinstance(resource_name, str) or not resource_name.strip():
            raise ValueError("Each resource must be a name or an object containing a name")
        resource_name = resource_name.strip()
        if resource_name in resource_ids:
            raise ValueError(f"Duplicate resource name in company file: '{resource_name}'")
        resource_ids[resource_name] = upsert_resource(cursor, company_id, resource)

    for item in architecture:
        if not isinstance(item, dict):
            raise ValueError("Each agent entry must be an object")
        agent_name = item.get("agent", item.get("name"))
        if not isinstance(agent_name, str) or not agent_name.strip():
            raise ValueError("Each agent must have a non-empty 'agent' or 'name'")
        agent_name = agent_name.strip()

        team_value = item.get("team", item.get("team_name"))
        if isinstance(team_value, dict):
            team_name = team_value.get("name")
            if not isinstance(team_name, str) or not team_name.strip():
                raise ValueError(f"Agent '{agent_name}' team object must include a name")
            team_name = team_name.strip()
            if team_name not in team_ids:
                team_ids[team_name] = upsert_team(cursor, company_id, team_value)
            team_id = team_ids[team_name]
        elif isinstance(team_value, str):
            team_name = team_value.strip()
            if team_name not in team_ids:
                team_ids[team_name] = upsert_team(cursor, company_id, team_name)
            team_id = team_ids[team_name]
        elif item.get("team_id") is not None:
            cursor.execute(
                "SELECT team_id FROM teams WHERE team_id = %s AND company_id = %s",
                (item["team_id"], company_id),
            )
            result = cursor.fetchone()
            if result is None:
                raise ValueError(f"team_id {item['team_id']} does not belong to company '{company_name}'")
            team_id = result[0]
        else:
            team_name = "Imported Team"
            if team_name not in team_ids:
                team_ids[team_name] = upsert_team(cursor, company_id, team_name)
            team_id = team_ids[team_name]

        cursor.execute("""
            INSERT INTO agents (company_id, name, purpose, team_id)
            VALUES (%s, %s, %s, %s)
        """, (company_id, agent_name, item.get("purpose", "Imported architectural component"), team_id))
        agent_id = cursor.lastrowid

        dependencies = item.get("dependencies", [])
        if not isinstance(dependencies, list):
            raise ValueError(f"Agent '{agent_name}' dependencies must be an array")
        for dependency in dependencies:
            if isinstance(dependency, str):
                resource_data = {"name": dependency.strip(), "resource_type": "TOOL"}
                dependency_type = item.get("dependency_type", "RUNTIME")
                is_critical = item.get("is_critical", True)
            elif isinstance(dependency, dict):
                resource_data = dependency.get("resource", dependency)
                dependency_type = dependency.get("dependency_type", item.get("dependency_type", "RUNTIME"))
                is_critical = dependency.get("is_critical", item.get("is_critical", True))
            else:
                raise ValueError(f"Dependencies for agent '{agent_name}' must be names or objects")
            if isinstance(resource_data, str):
                resource_data = {"name": resource_data.strip(), "resource_type": "TOOL"}
            resource_name = resource_data.get("name") if isinstance(resource_data, dict) else None
            if not isinstance(resource_name, str) or not resource_name.strip():
                raise ValueError(f"Dependency for agent '{agent_name}' must identify a resource")
            resource_name = resource_name.strip()
            resource_id = resource_ids.get(resource_name)
            if resource_id is None:
                resource_data = dict(resource_data)
                resource_data["name"] = resource_name
                resource_id = upsert_resource(cursor, company_id, resource_data)
                resource_ids[resource_name] = resource_id
            cursor.execute("""
                INSERT INTO agent_resources (agent_id, resource_id, dependency_type, is_critical)
                VALUES (%s, %s, %s, %s)
            """, (agent_id, resource_id, dependency_type, bool(is_critical)))

    for workflow in workflows:
        if not isinstance(workflow, dict) or not isinstance(workflow.get("name"), str):
            raise ValueError("Each workflow must be an object containing a name")
        workflow_name = workflow["name"].strip()
        team_value = workflow.get("team", "Imported Team")
        team_name = team_value.get("name") if isinstance(team_value, dict) else team_value
        if not isinstance(team_name, str) or not team_name.strip():
            raise ValueError(f"Workflow '{workflow_name}' must specify its team's name")
        team_name = team_name.strip()
        if team_name not in team_ids:
            team_ids[team_name] = upsert_team(cursor, company_id, team_value)
        cursor.execute("""
            INSERT INTO workflows (company_id, team_id, name, criticality_level, description)
            VALUES (%s, %s, %s, %s, %s)
        """, (company_id, team_ids[team_name], workflow_name,
              str(workflow.get("criticality_level", "MEDIUM")).upper(), workflow.get("description")))
        workflow_id = cursor.lastrowid
        workflow_ids[workflow_name] = workflow_id
        workflow_agents = workflow.get("agents", [])
        if not isinstance(workflow_agents, list):
            raise ValueError(f"Workflow '{workflow_name}' agents must be an array")
        for index, step in enumerate(workflow_agents, start=1):
            agent_name = step if isinstance(step, str) else step.get("agent", step.get("name"))
            if not isinstance(agent_name, str) or not agent_name.strip():
                raise ValueError(f"Workflow '{workflow_name}' includes an unnamed agent")
            cursor.execute("SELECT agent_id FROM agents WHERE company_id = %s AND name = %s",
                           (company_id, agent_name.strip()))
            result = cursor.fetchone()
            if result is None:
                raise ValueError(f"Workflow '{workflow_name}' references unknown agent '{agent_name}'")
            execution_step = step.get("execution_step", index) if isinstance(step, dict) else index
            cursor.execute("""
                INSERT INTO workflow_agents (workflow_id, agent_id, execution_step)
                VALUES (%s, %s, %s)
            """, (workflow_id, result[0], execution_step))

    return {
        "company": company_name,
        "teams_processed": len(team_ids),
        "resources_processed": len(resource_ids),
        "agents_processed": len(architecture),
        "workflows_processed": len(workflow_ids),
    }


@app.post("/api/ingest")
@require_permission("imports.manage")
def ingest_config():
    uploads = request.files.getlist("files") or request.files.getlist("file")
    if not uploads:
        return error_response("Upload one or more JSON files using the 'files' field")
    connection = cursor = None
    try:
        payloads = []
        for upload in uploads:
            payload = json.load(upload)
            if not isinstance(payload, dict):
                raise ValueError(f"'{upload.filename}' must contain a JSON object")
            payloads.append((upload.filename or "uploaded JSON", payload))
        company_names = []
        for filename, payload in payloads:
            company = payload.get("company")
            company_name = company.get("name") if isinstance(company, dict) else company
            if not isinstance(company_name, str) or not company_name.strip():
                raise ValueError(f"'{filename}' must include company.name")
            company_names.append(company_name.strip().casefold())
        if len(company_names) != len(set(company_names)):
            raise ValueError("A batch can contain only one JSON file per company")

        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor()
        summaries = [replace_company_payload(cursor, payload) for _, payload in payloads]
        connection.commit()
        return jsonify({"message": f"Replaced registry data for {len(summaries)} company(ies)",
                        "companies": summaries})
    except (mysql.connector.Error, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        if connection:
            connection.rollback()
        return error_response(f"Import rolled back; no company data was replaced: {error}")
    finally:
        close_db(cursor, connection)


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1", port=5000)
