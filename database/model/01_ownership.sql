USE ai_agent_registry;

CREATE TABLE IF NOT EXISTS companies (
    company_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(160) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (company_id),
    UNIQUE KEY uq_companies_name (name)
);

CREATE TABLE IF NOT EXISTS teams (
    team_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    company_id INT UNSIGNED NOT NULL,
    name VARCHAR(100) NOT NULL,
    lead_email VARCHAR(150) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (team_id),
    UNIQUE KEY uq_teams_company_name (company_id, name),
    UNIQUE KEY uq_teams_company_email (company_id, lead_email),
    CONSTRAINT fk_teams_company FOREIGN KEY (company_id)
        REFERENCES companies (company_id) ON UPDATE CASCADE ON DELETE RESTRICT
);

-- propagates a change to a referenced key to dependent rows
-- prevents deleting a company while dependent teams still reference it
