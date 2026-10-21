USE ai_agent_registry;

-- Upgrade databases installed before company JSON imports were supported.
-- New installs define this column as nullable in 01_ownership.sql.
ALTER TABLE teams
    MODIFY COLUMN lead_email VARCHAR(150) NULL;
