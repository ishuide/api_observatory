USE ai_agent_registry;

-- Registry overview: agent ownership and dependency count.
SELECT a.agent_id, a.name, t.name AS team_name, a.status,
       COUNT(ar.resource_id) AS dependency_count
FROM agents AS a
JOIN teams AS t ON t.team_id = a.team_id
LEFT JOIN agent_resources AS ar ON ar.agent_id = a.agent_id
GROUP BY a.agent_id, a.name, t.name, a.status
ORDER BY t.name, a.name;

-- Resource exposure: current health and critical dependent agents.
SELECT r.resource_id, r.name, r.resource_type, r.status,
       COUNT(CASE WHEN ar.is_critical THEN ar.agent_id END) AS critical_agent_count
FROM resources AS r
LEFT JOIN agent_resources AS ar ON ar.resource_id = r.resource_id
GROUP BY r.resource_id, r.name, r.resource_type, r.status
ORDER BY critical_agent_count DESC, r.name;

-- Workflow execution order, used to understand downstream impact.
SELECT w.name AS workflow_name, w.criticality_level, wa.execution_step,
       a.name AS agent_name, a.status AS agent_status
FROM workflows AS w
JOIN workflow_agents AS wa ON wa.workflow_id = w.workflow_id
JOIN agents AS a ON a.agent_id = wa.agent_id
ORDER BY w.name, wa.execution_step;

-- Recursive impact query: change resource_id 1 to investigate another resource.
WITH RECURSIVE impacted_agents (agent_id, depth) AS (
    SELECT ar.agent_id, 1
    FROM agent_resources AS ar
    WHERE ar.resource_id = 1 AND ar.is_critical = TRUE
    UNION DISTINCT
    SELECT next_agent.agent_id, impacted.depth + 1
    FROM impacted_agents AS impacted
    JOIN workflow_agents AS current_step ON current_step.agent_id = impacted.agent_id
    JOIN workflow_agents AS next_step
      ON next_step.workflow_id = current_step.workflow_id
     AND next_step.execution_step > current_step.execution_step
    JOIN agents AS next_agent ON next_agent.agent_id = next_step.agent_id
    WHERE impacted.depth < 10
)
SELECT a.agent_id, a.name AS impacted_agent, MIN(impacted.depth) AS hop_depth,
       GROUP_CONCAT(DISTINCT w.name ORDER BY w.name SEPARATOR ', ') AS workflows
FROM impacted_agents AS impacted
JOIN agents AS a ON a.agent_id = impacted.agent_id
LEFT JOIN workflow_agents AS wa ON wa.agent_id = a.agent_id
LEFT JOIN workflows AS w ON w.workflow_id = wa.workflow_id
GROUP BY a.agent_id, a.name
ORDER BY hop_depth, a.name;

-- Recent audit history shown in the application.
SELECT log_id, table_name, operation, record_id, changed_by, change_details, created_at
FROM audit_logs
ORDER BY created_at DESC, log_id DESC
LIMIT 50;
