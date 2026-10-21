USE ai_agent_registry;

-- Registry entities: autonomous agents and the infrastructure they consume.
CREATE TABLE IF NOT EXISTS resources (
    resource_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    company_id INT UNSIGNED NOT NULL,
    name VARCHAR(120) NOT NULL,
    resource_type ENUM('LLM', 'API', 'VECTOR_DB', 'MEMORY', 'TOOL') NOT NULL,
    endpoint_url VARCHAR(500) NULL,
    status ENUM('HEALTHY', 'DEGRADED', 'OFFLINE') NOT NULL DEFAULT 'HEALTHY',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (resource_id),
    UNIQUE KEY uq_resources_company_name (company_id, name),
    KEY idx_resources_status (status),
    CONSTRAINT fk_resources_company FOREIGN KEY (company_id)
        REFERENCES companies (company_id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS agents (
    agent_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    company_id INT UNSIGNED NOT NULL,
    team_id INT UNSIGNED NOT NULL,
    name VARCHAR(120) NOT NULL,
    purpose TEXT NOT NULL,
    status ENUM('ACTIVE', 'DISABLED', 'DEPRECATED') NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (agent_id),
    UNIQUE KEY uq_agents_company_name (company_id, name),
    KEY idx_agents_team_status (team_id, status),
    CONSTRAINT fk_agents_company FOREIGN KEY (company_id)
        REFERENCES companies (company_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_agents_team FOREIGN KEY (team_id)
        REFERENCES teams (team_id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;
