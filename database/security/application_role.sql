-- DCL: create a reusable least-privilege role for the Flask application.
-- Run this using a MySQL administrator account after installing the schema.
USE ai_agent_registry;

CREATE ROLE IF NOT EXISTS 'ai_registry_app';

GRANT SELECT, INSERT, UPDATE ON ai_agent_registry.companies TO 'ai_registry_app';
GRANT SELECT ON ai_agent_registry.teams TO 'ai_registry_app';
GRANT SELECT, INSERT, UPDATE, DELETE ON ai_agent_registry.teams TO 'ai_registry_app';
GRANT SELECT, INSERT, UPDATE, DELETE ON ai_agent_registry.workflows TO 'ai_registry_app';
GRANT SELECT, INSERT, UPDATE ON ai_agent_registry.workflow_agents TO 'ai_registry_app';
GRANT SELECT ON ai_agent_registry.audit_logs TO 'ai_registry_app';
GRANT SELECT, INSERT, UPDATE, DELETE ON ai_agent_registry.agents TO 'ai_registry_app';
GRANT SELECT, INSERT, UPDATE, DELETE ON ai_agent_registry.resources TO 'ai_registry_app';
GRANT SELECT, INSERT, UPDATE, DELETE ON ai_agent_registry.agent_resources TO 'ai_registry_app';
GRANT SELECT ON ai_agent_registry.app_roles TO 'ai_registry_app';
GRANT SELECT ON ai_agent_registry.app_permissions TO 'ai_registry_app';
GRANT SELECT, INSERT, UPDATE ON ai_agent_registry.app_users TO 'ai_registry_app';
GRANT SELECT, INSERT, DELETE ON ai_agent_registry.app_user_roles TO 'ai_registry_app';
GRANT SELECT ON ai_agent_registry.app_role_permissions TO 'ai_registry_app';
GRANT EXECUTE ON PROCEDURE ai_agent_registry.deactivate_resource_and_cascade TO 'ai_registry_app';
GRANT EXECUTE ON PROCEDURE ai_agent_registry.recover_resource TO 'ai_registry_app';

-- After creating a dedicated MySQL user, assign the role and make it active:
-- GRANT 'ai_registry_app' TO 'ai_registry_user'@'localhost';
-- SET DEFAULT ROLE 'ai_registry_app' TO 'ai_registry_user'@'localhost';
