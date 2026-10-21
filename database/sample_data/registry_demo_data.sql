USE ai_agent_registry;

INSERT INTO companies (name) VALUES ('AI Agent Demo Company')
ON DUPLICATE KEY UPDATE company_id = LAST_INSERT_ID(company_id);
SET @demo_company_id = (SELECT company_id FROM companies WHERE name = 'AI Agent Demo Company');

INSERT INTO teams (company_id, name, lead_email) VALUES
    (@demo_company_id, 'Core Engineering', 'core@example.com'),
    (@demo_company_id, 'Platform Operations', 'platform@example.com')
ON DUPLICATE KEY UPDATE lead_email = VALUES(lead_email);

INSERT INTO resources (company_id, name, resource_type, endpoint_url, status) VALUES
    (@demo_company_id, 'GPT-4o', 'LLM', 'https://api.openai.com/v1', 'HEALTHY'),
    (@demo_company_id, 'Claude Sonnet', 'LLM', 'https://api.anthropic.com/v1', 'HEALTHY'),
    (@demo_company_id, 'GitHub REST API', 'API', 'https://api.github.com', 'HEALTHY'),
    (@demo_company_id, 'Pinecone Vector Index', 'VECTOR_DB', 'https://api.pinecone.io', 'HEALTHY'),
    (@demo_company_id, 'Redis Shared Memory', 'MEMORY', NULL, 'HEALTHY')
ON DUPLICATE KEY UPDATE
    resource_type = VALUES(resource_type), endpoint_url = VALUES(endpoint_url);

INSERT INTO agents (company_id, team_id, name, purpose, status)
SELECT t.company_id, t.team_id, seed.name, seed.purpose, 'ACTIVE'
FROM (
    SELECT 'Core Engineering' AS team_name, 'Code Reviewer Agent' AS name,
           'Performs automated reviews' AS purpose
    UNION ALL
    SELECT 'Platform Operations', 'Deployment Agent', 'Coordinates cloud releases'
    UNION ALL
    SELECT 'Core Engineering', 'Data Extraction Agent', 'Parses incoming unstructured documents'
    UNION ALL
    SELECT 'Platform Operations', 'Security Compliance Agent', 'Audits generated changes against security advisories'
) AS seed
JOIN teams AS t ON t.company_id = @demo_company_id AND t.name = seed.team_name
ON DUPLICATE KEY UPDATE purpose = VALUES(purpose), team_id = VALUES(team_id), company_id = VALUES(company_id);

INSERT INTO workflows (company_id, team_id, name, criticality_level, description)
SELECT t.company_id, t.team_id, 'Autonomous Change Review', 'CRITICAL',
       'Generate, review, and prepare a change for release.'
FROM teams AS t
WHERE t.company_id = @demo_company_id AND t.name = 'Core Engineering'
ON DUPLICATE KEY UPDATE criticality_level = VALUES(criticality_level), company_id = VALUES(company_id);

INSERT IGNORE INTO agent_resources (agent_id, resource_id, dependency_type, is_critical)
SELECT a.agent_id, r.resource_id, seed.dependency_type, seed.is_critical
FROM (
    SELECT 'Code Reviewer Agent' AS agent_name, 'Claude Sonnet' AS resource_name,
           'INFERENCE' AS dependency_type, TRUE AS is_critical
    UNION ALL SELECT 'Code Reviewer Agent', 'GitHub REST API', 'REVIEW', TRUE
    UNION ALL SELECT 'Deployment Agent', 'GitHub REST API', 'RELEASE', TRUE
    UNION ALL SELECT 'Data Extraction Agent', 'GPT-4o', 'INFERENCE', TRUE
    UNION ALL SELECT 'Data Extraction Agent', 'Pinecone Vector Index', 'RETRIEVAL', TRUE
    UNION ALL SELECT 'Security Compliance Agent', 'GitHub REST API', 'SOURCE_ACCESS', TRUE
    UNION ALL SELECT 'Security Compliance Agent', 'Claude Sonnet', 'INFERENCE', FALSE
) AS seed
JOIN agents AS a ON a.company_id = @demo_company_id AND a.name = seed.agent_name
JOIN resources AS r ON r.company_id = @demo_company_id AND r.name = seed.resource_name;

INSERT IGNORE INTO workflow_agents (workflow_id, agent_id, execution_step)
SELECT w.workflow_id, a.agent_id, seed.execution_step
FROM (
    SELECT 'Autonomous Change Review' AS workflow_name,
           'Data Extraction Agent' AS agent_name, 1 AS execution_step
    UNION ALL SELECT 'Autonomous Change Review', 'Code Reviewer Agent', 2
    UNION ALL SELECT 'Autonomous Change Review', 'Security Compliance Agent', 3
    UNION ALL SELECT 'Autonomous Change Review', 'Deployment Agent', 4
) AS seed
JOIN workflows AS w ON w.company_id = @demo_company_id AND w.name = seed.workflow_name
JOIN agents AS a ON a.company_id = @demo_company_id AND a.name = seed.agent_name;
