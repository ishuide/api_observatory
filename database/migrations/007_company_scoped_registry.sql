USE ai_agent_registry;

-- Upgrade the existing single-registry database without deleting its data.
CREATE TABLE IF NOT EXISTS companies (
    company_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(160) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (company_id),
    UNIQUE KEY uq_companies_name (name)
) ENGINE=InnoDB;

INSERT INTO companies (name)
VALUES ('Legacy Registry')
ON DUPLICATE KEY UPDATE company_id = LAST_INSERT_ID(company_id);

SET @legacy_company_id = (SELECT company_id FROM companies WHERE name = 'Legacy Registry');

ALTER TABLE teams
    ADD COLUMN company_id INT UNSIGNED NULL AFTER team_id,
    DROP INDEX uq_teams_name,
    DROP INDEX uq_teams_lead_email;
UPDATE teams SET company_id = @legacy_company_id WHERE company_id IS NULL;
ALTER TABLE teams
    MODIFY COLUMN company_id INT UNSIGNED NOT NULL,
    ADD UNIQUE KEY uq_teams_company_name (company_id, name),
    ADD UNIQUE KEY uq_teams_company_email (company_id, lead_email),
    ADD CONSTRAINT fk_teams_company FOREIGN KEY (company_id)
        REFERENCES companies (company_id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE resources
    ADD COLUMN company_id INT UNSIGNED NULL AFTER resource_id,
    DROP INDEX uq_resources_name;
UPDATE resources SET company_id = @legacy_company_id WHERE company_id IS NULL;
ALTER TABLE resources
    MODIFY COLUMN company_id INT UNSIGNED NOT NULL,
    ADD UNIQUE KEY uq_resources_company_name (company_id, name),
    ADD CONSTRAINT fk_resources_company FOREIGN KEY (company_id)
        REFERENCES companies (company_id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE agents
    ADD COLUMN company_id INT UNSIGNED NULL AFTER agent_id,
    DROP INDEX uq_agents_name;
UPDATE agents AS a
JOIN teams AS t ON t.team_id = a.team_id
SET a.company_id = t.company_id
WHERE a.company_id IS NULL;
ALTER TABLE agents
    MODIFY COLUMN company_id INT UNSIGNED NOT NULL,
    ADD UNIQUE KEY uq_agents_company_name (company_id, name),
    ADD CONSTRAINT fk_agents_company FOREIGN KEY (company_id)
        REFERENCES companies (company_id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE workflows
    ADD COLUMN company_id INT UNSIGNED NULL AFTER workflow_id,
    DROP INDEX uq_workflows_name;
UPDATE workflows AS w
JOIN teams AS t ON t.team_id = w.team_id
SET w.company_id = t.company_id
WHERE w.company_id IS NULL;
ALTER TABLE workflows
    MODIFY COLUMN company_id INT UNSIGNED NOT NULL,
    ADD UNIQUE KEY uq_workflows_company_name (company_id, name),
    ADD CONSTRAINT fk_workflows_company FOREIGN KEY (company_id)
        REFERENCES companies (company_id) ON UPDATE CASCADE ON DELETE RESTRICT;
