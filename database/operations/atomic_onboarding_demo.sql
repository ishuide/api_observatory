USE ai_agent_registry;

-- Demonstrate the same all-or-nothing workflow used by the Atomic Onboard UI.
-- Uses a unique name so it can be run repeatedly against demo data.
SET @demo_agent_name = CONCAT('Transaction Demo ', UUID());

START TRANSACTION;

INSERT INTO agents (team_id, name, purpose, status)
VALUES (1, @demo_agent_name, 'Demonstrates transactional onboarding', 'ACTIVE');
SET @demo_agent_id = LAST_INSERT_ID();
SAVEPOINT agent_created;

INSERT INTO agent_resources (agent_id, resource_id, dependency_type, is_critical)
VALUES (@demo_agent_id, 1, 'RUNTIME', TRUE);

INSERT INTO workflow_agents (workflow_id, agent_id, execution_step)
SELECT w.workflow_id, @demo_agent_id,
       (SELECT COALESCE(MAX(existing_step.execution_step), 0) + 1
    FROM workflow_agents AS existing_step
    WHERE existing_step.workflow_id = w.workflow_id)
FROM workflows AS w
WHERE w.workflow_id = 1;

-- A failure before COMMIT rolls the agent and all associations back together.
-- To practice partial rollback, uncomment the next line, then COMMIT:
-- ROLLBACK TO SAVEPOINT agent_created;
COMMIT;

SELECT a.agent_id, a.name, ar.resource_id, wa.workflow_id, wa.execution_step
FROM agents AS a
LEFT JOIN agent_resources AS ar ON ar.agent_id = a.agent_id
LEFT JOIN workflow_agents AS wa ON wa.agent_id = a.agent_id
WHERE a.name = @demo_agent_name;
