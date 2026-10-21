USE ai_agent_registry;

-- Normalization rationale for the AI Agent Ecosystem Registry.
--
-- First Normal Form (1NF): values are atomic; no agent stores a comma-separated
-- team, resource, or workflow list. Every relationship is represented by rows.
--
-- Second Normal Form (2NF): relationship attributes depend on each complete
-- composite key. In agent_resources, dependency_type/is_critical depend on
-- (agent_id, resource_id); execution_step depends on (workflow_id, agent_id).
--
-- Third Normal Form (3NF): descriptive attributes are stored with their
-- determinant entity. Team names are in teams, resource details in resources,
-- agent details in agents, and workflow details in workflows. The team name is
-- not duplicated in agents, and resource names are not duplicated in links.
--
-- Functional dependencies:
-- team_id -> name, lead_email, created_at
-- resource_id -> name, resource_type, endpoint_url, status, created_at
-- agent_id -> team_id, name, purpose, status, created_at, updated_at
-- workflow_id -> team_id, name, criticality_level, description, created_at
-- (agent_id, resource_id) -> dependency_type, is_critical, created_at
-- (workflow_id, agent_id) -> execution_step
--
-- Inspect the implemented key structure and constraints:
SHOW TABLES;

SELECT TABLE_NAME, COLUMN_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME,
       REFERENCED_COLUMN_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = DATABASE()
ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION;
