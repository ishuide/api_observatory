USE ai_agent_registry;

-- Central event history populated by feature triggers and stored routines.
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    table_name VARCHAR(64) NOT NULL,
    operation VARCHAR(40) NOT NULL,
    record_id BIGINT UNSIGNED NOT NULL,
    changed_by VARCHAR(288) NOT NULL,
    change_details JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (log_id),
    KEY idx_audit_created (created_at),
    KEY idx_audit_record (table_name, record_id)
) ENGINE=InnoDB;
