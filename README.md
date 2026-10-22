# AI Agent Ecosystem Registry

A single database-backed project for registering AI agents, teams, resources, and workflows; maintaining agent/resource dependencies; exploring the dependency graph; and demonstrating core DBMS concepts through a React web interface and a MySQL 8 database.

## Architecture

```text
React + Vite frontend  -->  Flask REST API  -->  MySQL 8
                              |                   |
                              |                   +-- normalized relational schema
                              |                   +-- constraints and indexes
                              |                   +-- integrity and audit triggers
                              |                   +-- outage/recovery stored procedures
                              |                   +-- transaction-backed operations
                              +-- SQL queries for overview and blast radius
```

The frontend is served at a Vite URL such as `http://127.0.0.1:5173/`; the backend API listens on port `5000`. The backend is API-only, so its `/` URL is not a web page. By default, React calls port 5000 on the same hostname used to open the frontend, so session cookies work with either `localhost` or `127.0.0.1`. Override the API URL with `VITE_API_URL` in `frontend/.env.local` when needed.

## Features

- Registry overview of agents, teams, resources, workflows, and dependencies.
- Interactive graph of live agent-to-resource relationships.
- Recursive workflow blast-radius analysis when a critical resource fails.
- Database-triggered audit records and prevention of new links to offline resources.
- Stored procedures for resource cascade deactivation and recovery.
- Company snapshot imports: upload one or many JSON files; each file fully replaces only that company's teams, resources, agents, dependencies, and workflows.
- Manual agent and resource management: create/edit agents, create/edit/delete resources, and manage resource health.
- Database-backed application RBAC with `Admin`, `Operator`, and `Viewer` roles.

## Requirements

- MySQL Server 8.0 or later, plus the MySQL command-line client (`mysql`).
- Conda with an environment named `ai` and Python 3.12 (the run commands below use the user's local Anaconda path).
- Node.js and npm compatible with the Vite version in `frontend/package-lock.json`.

## Project Layout

```text
DBMS/
|-- backend/
|   |-- app.py
|   |-- create_admin.py
|   |-- requirements.txt
|   `-- test_app.py
|-- database/
|   |-- INSTALL.md
|   |-- migrations/
|   |-- bootstrap/
|   |-- model/
|   |-- sample_data/
|   |-- features/
|   |-- analytics/
|   |-- security/
|   `-- design/
|-- frontend/
|   |-- src/
|   |-- package.json
|   `-- vite.config.js
|-- samples/
|   `-- example-architecture.json
`-- README.md
```

## Database Setup

Start MySQL Server first. The detailed, ordered setup command list is maintained in [`database/INSTALL.md`](database/INSTALL.md). SQL files are grouped by lifecycle and domain responsibility rather than by statement category:

- `bootstrap/`: create the application database.
- `model/`: create ownership, registry entities, workflow relationships, and audit storage in foreign-key order; includes a migration for existing databases to support self-service company imports.
- `sample_data/`: populate the demo teams, agents, resources, dependencies, and workflow.
- `features/`: implement dependency governance and resource health behavior, including their triggers and stored procedures.
- `analytics/`: queries for registry health, exposure, workflows, and recursive failure impact.
- `security/`: a least-privilege application role (DCL).
- `design/`: normalization rationale and relational model inspection queries.

Setup scripts are non-destructive to existing tables. Run them in order on a new or appropriately prepared database. Feature scripts drop and recreate only their own triggers/procedures when rerun.

For a fresh database, run `database/INSTALL.md` in order. If your current database predates company scoping, run the tenant migration once from the project root:

```zsh
mysql -u root -p ai_agent_registry < database/model/05_import_compatibility.sql
mysql -u root -p < database/migrations/007_company_scoped_registry.sql
mysql -u root -p < database/migrations/006_application_rbac.sql
mysql -u root -p < database/security/application_role.sql
```

Do not run `007_company_scoped_registry.sql` on a fresh database or rerun it after it has succeeded. It assigns existing records to `Legacy Registry` and changes table indexes/columns.

Create the first application administrator interactively after installing the RBAC migration:

```zsh
cd ~/Downloads/DBMS/backend
python create_admin.py
```

It prompts for the account name and password and stores only a Werkzeug password hash. No default admin password is seeded.

## Run the Application

Keep the backend and frontend running in separate terminals.

### Terminal 1: Flask API

```zsh
source /opt/anaconda3/etc/profile.d/conda.sh
conda activate ai
cd ~/Downloads/DBMS
python -m pip install -r backend/requirements.txt

export DB_HOST="127.0.0.1"
export DB_PORT="3306"
export DB_NAME="ai_agent_registry"
export DB_USER="root"
export DB_PASSWORD="your_mysql_password"
export FLASK_DEBUG="1"
export FLASK_SECRET_KEY="a-long-random-private-value"

cd backend
python app.py
```

Use the same MySQL credentials that you used to set up the database. For a real deployment, create a dedicated least-privilege MySQL application user rather than running the application as `root`.

### Terminal 2: React frontend

```zsh
cd ~/Downloads/DBMS/frontend
npm install
npm run dev -- --host 127.0.0.1
```

Open **http://127.0.0.1:5173/**. For a different backend URL, create `frontend/.env.local` using `frontend/.env.example` as a template and set `VITE_API_URL` (for example, `http://127.0.0.1:5000/api`). Restart Vite after changing environment values.

## SQL Concepts Demonstrated

- **DDL and normalization:** `database/model/` defines a 3NF model with entity and junction tables; `database/design/normalization_and_model.sql` documents functional dependencies and introspects implemented keys.
- **DML:** `database/sample_data/registry_demo_data.sql` seeds realistic registry data idempotently; the Flask API performs application writes using parameterized statements.
- **Integrity and indexing:** primary/unique keys, foreign keys, constrained status/type values, and indexes enforce valid relationships and support registry, graph, audit, and impact lookups.
- **Triggers:** `database/features/dependency_governance.sql` blocks attaching agents to offline resources and records dependency additions/removals. `database/features/resource_health_management.sql` audits resource and agent status transitions.
- **Stored procedures:** resource health procedures in `database/features/resource_health_management.sql` provide the UI's cascade-failure and recovery actions.
- **Queries:** `database/analytics/registry_questions.sql` implements the registry reports and recursive CTE used for business impact analysis.
- **DCL:** `database/security/application_role.sql` creates a least-privilege role for the Flask application rather than granting it database administrator access.
- **Application RBAC:** `database/migrations/006_application_rbac.sql` stores users, roles, permissions, and their assignments. Flask verifies password hashes and enforces database-loaded permissions at the API.

The model is in third normal form: team, agent, resource, and workflow attributes are stored once in their owning entity tables. The many-to-many relationships use `agent_resources` and `workflow_agents` junction tables.

## Company JSON Import

Use the **Import JSON** control to select one JSON file or multiple files at once. Every file must declare a `company.name`. Reimporting a company is a full snapshot replacement: existing teams, resources, agents, dependencies, and workflows for that company are removed and rebuilt to match that file. Records for other companies remain untouched. Files in a multi-file upload are processed in one transaction; an error in any file rolls back the whole batch. Make each file a complete company snapshot, not a partial patch.

Example imports are available in `samples/`: `company-small.json` is a small one-team setup, `example-architecture.json` is the general demo company, `company-research.json` models a multi-team research workflow, and `company-operations.json` models a multi-step production release. Each represents a distinct company snapshot and can be selected individually or together. The general shape is:

```json
{
    "teams": [{"name": "Example Company AI", "lead_email": "ai@example.com"}],
    "resources": [{"name": "Company Inference API", "resource_type": "API", "endpoint_url": "https://api.example.com"}],
    "architecture": [{
        "agent": "Research Agent",
        "purpose": "Finds company knowledge",
        "team": "Example Company AI",
        "dependencies": [{"name": "Company Inference API", "dependency_type": "INFERENCE", "is_critical": true}]
    }],
    "workflows": [{"name": "Assisted Research", "team": "Example Company AI", "criticality_level": "HIGH", "agents": ["Research Agent"]}]
}
```

`teams`, `resources`, and `workflows` are optional arrays. Teams may be strings or objects; resources may be strings or objects. Agents can use `team` or `team_name` instead of numeric `team_id`. Existing files that use `team_id` remain supported.

## Feature-to-Concept Mapping

| Application feature | Database concepts applied | User value |
| --- | --- | --- |
| Dependency binding | Junction table, foreign keys, trigger, audit log | Prevents invalid links and records architecture changes |
| Resource outage simulation | Recursive CTE, stored procedure, transaction, status triggers | Shows which agents/workflows are affected and updates their state consistently |
| Resource recovery | Stored procedure, conditional update, status triggers | Restores healthy service without reactivating agents that still have another critical offline dependency |
| Registry overview and graph | Normalized joins, aggregate queries, indexes | Presents consistent current ownership and dependency information |
| Audit view | Trigger-written audit rows, indexed chronological query | Makes operational changes visible to project users |
| User access management | RBAC junction tables and API permission checks | Admins control who can view, operate, or administer the registry |

### Application Roles

| Role | Access |
| --- | --- |
| `Admin` | All registry and user-management permissions |
| `Operator` | View/audit and manage agents, resources, dependencies, resource health, and imports |
| `Viewer` | Read registry, impact analysis, and audit history only |

Login uses HTTP-only session cookies and CSRF tokens on write requests. The frontend hides controls the current role cannot use, while the backend enforces the actual access decision. Set a private, stable `FLASK_SECRET_KEY` so sessions survive backend restarts. For HTTPS deployments set `SESSION_COOKIE_SECURE=1`.

## API Routes

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/overview` | Return registry data and dropdown options |
| `POST` | `/api/auth/login` | Authenticate and start a session |
| `GET` | `/api/auth/me` | Return current user roles and permissions |
| `POST` | `/api/auth/logout` | End the current session |
| `GET` | `/api/admin/users` | List accounts (Admin) |
| `POST` | `/api/admin/users` | Create an account and assign a role (Admin) |
| `PUT` | `/api/admin/users/<user_id>` | Change role or enable/disable account (Admin) |
| `POST` | `/api/agents` | Register an agent |
| `PUT` | `/api/agents/<agent_id>` | Edit an agent |
| `DELETE` | `/api/agents/<agent_id>` | Delete an agent |
| `POST` | `/api/resources` | Create a resource |
| `PUT` | `/api/resources/<resource_id>` | Edit a resource and its health status |
| `DELETE` | `/api/resources/<resource_id>` | Delete an unreferenced resource |
| `POST` | `/api/dependencies` | Link an agent and resource |
| `DELETE` | `/api/dependencies/<agent_id>/<resource_id>` | Remove a dependency |
| `POST` | `/api/resources/<resource_id>/deactivate` | Call the cascade deactivation procedure |
| `POST` | `/api/resources/<resource_id>/recover` | Call the recovery procedure |
| `GET` | `/api/impact/<resource_id>` | Return recursive workflow impact |
| `GET` | `/api/audit` | Return recent database audit entries |
| `POST` | `/api/ingest` | Ingest an uploaded architecture JSON file |

## Tests and Build

```zsh
# Backend unit tests; no live database is required for these mocked API tests.
cd ~/Downloads/DBMS
/opt/anaconda3/envs/ai/bin/python -m pytest -q backend/test_app.py

# Frontend checks
cd frontend
npm run lint
npm run build
```

## Remaining Work

- Configure a MySQL account with application permissions and verify the ordered SQL setup against the actual local server. The local MySQL client is installed, but the current shell could not authenticate as `root` without a password, so a live database run was not verified here.
- Add integration tests using a disposable MySQL database to verify triggers, stored procedures, foreign keys, and recursive query behavior.
- Review whether workflow editing and resource CRUD are required for the project rubric; the current UI focuses on registry, dependencies, impact, and monitoring.
- For deployment, disable Flask debug mode, configure an explicit trusted CORS origin, use a secret manager, and run Flask behind a production WSGI server.
