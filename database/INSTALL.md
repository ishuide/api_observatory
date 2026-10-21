# Database Installation

Target engine: MySQL 8.0 or later. These commands assume a MySQL administrator account and are run from the project root.

## Fresh database

The current model already includes company ownership. Create a new, empty database and apply scripts in this order:

```zsh
mysql -u root -p < database/bootstrap/00_create_database.sql
mysql -u root -p < database/model/01_ownership.sql
mysql -u root -p < database/model/02_registry_entities.sql
mysql -u root -p < database/model/03_workflows_and_relationships.sql
mysql -u root -p < database/model/04_audit_store.sql
mysql -u root -p < database/migrations/006_application_rbac.sql
mysql -u root -p < database/migrations/007_company_scoped_registry.sql
mysql -u root -p < database/sample_data/registry_demo_data.sql
mysql -u root -p < database/features/dependency_governance.sql
mysql -u root -p < database/features/resource_health_management.sql
mysql -u root -p < database/security/application_role.sql
```

Do **not** run migration `007_company_scoped_registry.sql` on a fresh database; the fresh schema already has those columns and indexes.

## Existing database upgrade

For the existing single-company schema installed before tenant scoping, apply this migration **once**. It preserves current registry data by assigning it to `Legacy Registry`:

```zsh
mysql -u root -p ai_agent_registry < database/model/05_import_compatibility.sql
mysql -u root -p < database/migrations/006_application_rbac.sql
mysql -u root -p < database/migrations/007_company_scoped_registry.sql
mysql -u root -p < database/security/application_role.sql
```

Do not rerun `007_company_scoped_registry.sql`: MySQL DDL migrations are not transactional, and the migration alters existing columns/indexes.

## First administrator

After schema/RBAC setup, create an initial app administrator interactively:

```zsh
cd ~/Downloads/DBMS/backend
python create_admin.py
```

It prompts for a username/password and stores a Werkzeug password hash. It does not seed a default password.

## Demo and coursework scripts

- `sample_data/registry_demo_data.sql`: sample data for `AI Agent Demo Company`.
- `analytics/registry_questions.sql`: read-only registry and impact queries.
- `operations/atomic_onboarding_demo.sql`: a transaction demo; run against a disposable database because it commits a row.
- `design/normalization_and_model.sql`: normalization explanation and key inspection.

## Import semantics

Every imported JSON document is a complete snapshot for one company and must include `company.name`. Reimporting replaces that company's teams, resources, agents, dependency links, and workflows. Other companies are left untouched. A multi-file batch is atomic across all included companies; a validation/database error rolls back every replacement in that request. Include every desired record in each company's file because omitted records for that company are removed.
