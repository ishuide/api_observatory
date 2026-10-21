USE ai_agent_registry;

-- Workflow definitions and the two many-to-many relationship tables.
CREATE TABLE IF NOT EXISTS workflows (
    workflow_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    company_id INT UNSIGNED NOT NULL,
    team_id INT UNSIGNED NOT NULL,
    name VARCHAR(120) NOT NULL,
    criticality_level ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL') NOT NULL DEFAULT 'MEDIUM',
    description VARCHAR(500) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workflow_id),
    UNIQUE KEY uq_workflows_company_name (company_id, name),
    KEY idx_workflows_team (team_id),
    CONSTRAINT fk_workflows_company FOREIGN KEY (company_id)
        REFERENCES companies (company_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_workflows_team FOREIGN KEY (team_id)
        REFERENCES teams (team_id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS agent_resources (
    agent_id INT UNSIGNED NOT NULL,
    resource_id INT UNSIGNED NOT NULL,
    dependency_type VARCHAR(50) NOT NULL DEFAULT 'RUNTIME',
    is_critical BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (agent_id, resource_id),
    KEY idx_agent_resources_resource (resource_id, is_critical),
    CONSTRAINT fk_agent_resources_agent FOREIGN KEY (agent_id)
        REFERENCES agents (agent_id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_agent_resources_resource FOREIGN KEY (resource_id)
        REFERENCES resources (resource_id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS workflow_agents (
    workflow_id INT UNSIGNED NOT NULL,
    agent_id INT UNSIGNED NOT NULL,
    execution_step INT UNSIGNED NOT NULL,
    PRIMARY KEY (workflow_id, agent_id),
    UNIQUE KEY uq_workflow_execution_step (workflow_id, execution_step),
    KEY idx_workflow_agents_agent (agent_id),
    CONSTRAINT fk_workflow_agents_workflow FOREIGN KEY (workflow_id)
        REFERENCES workflows (workflow_id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_workflow_agents_agent FOREIGN KEY (agent_id)
        REFERENCES agents (agent_id) ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;
