USE ai_agent_registry;

-- Resource health feature: audit status changes and cascade failure/recovery.
DROP TRIGGER IF EXISTS trg_agent_status_audit;
DROP TRIGGER IF EXISTS trg_resource_status_audit;
DROP PROCEDURE IF EXISTS deactivate_resource_and_cascade;
DROP PROCEDURE IF EXISTS recover_resource;

DELIMITER $$

CREATE TRIGGER trg_agent_status_audit
AFTER UPDATE ON agents
FOR EACH ROW
BEGIN
    IF OLD.status <> NEW.status THEN
        INSERT INTO audit_logs (table_name, operation, record_id, changed_by, change_details)
        VALUES ('agents', 'STATUS_CHANGED', NEW.agent_id, CURRENT_USER(),
                JSON_OBJECT('old_status', OLD.status, 'new_status', NEW.status));
    END IF;
END$$

CREATE TRIGGER trg_resource_status_audit
AFTER UPDATE ON resources
FOR EACH ROW
BEGIN
    IF OLD.status <> NEW.status THEN
        INSERT INTO audit_logs (table_name, operation, record_id, changed_by, change_details)
        VALUES ('resources', 'STATUS_CHANGED', NEW.resource_id, CURRENT_USER(),
                JSON_OBJECT('old_status', OLD.status, 'new_status', NEW.status));
    END IF;
END$$

CREATE PROCEDURE deactivate_resource_and_cascade(
    IN p_resource_id INT UNSIGNED,
    IN p_reason VARCHAR(500)
)
BEGIN
    DECLARE affected_resource_id INT UNSIGNED DEFAULT NULL;

    SELECT resource_id INTO affected_resource_id
    FROM resources
    WHERE resource_id = p_resource_id
    FOR UPDATE;

    IF affected_resource_id IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Resource does not exist';
    END IF;

    UPDATE resources
    SET status = 'OFFLINE'
    WHERE resource_id = p_resource_id;

    UPDATE agents AS a
    JOIN agent_resources AS ar ON ar.agent_id = a.agent_id
    SET a.status = 'DISABLED'
    WHERE ar.resource_id = p_resource_id
      AND ar.is_critical = TRUE
      AND a.status = 'ACTIVE';

    INSERT INTO audit_logs (table_name, operation, record_id, changed_by, change_details)
    VALUES ('resources', 'CASCADE_DEACTIVATED', p_resource_id, CURRENT_USER(),
            JSON_OBJECT('reason', COALESCE(p_reason, 'No reason supplied')));
END$$

CREATE PROCEDURE recover_resource(IN p_resource_id INT UNSIGNED)
BEGIN
    DECLARE affected_resource_id INT UNSIGNED DEFAULT NULL;

    SELECT resource_id INTO affected_resource_id
    FROM resources
    WHERE resource_id = p_resource_id
    FOR UPDATE;

    IF affected_resource_id IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Resource does not exist';
    END IF;

    UPDATE resources SET status = 'HEALTHY' WHERE resource_id = p_resource_id;

    UPDATE agents AS a
    JOIN agent_resources AS recovered_dep
      ON recovered_dep.agent_id = a.agent_id
     AND recovered_dep.resource_id = p_resource_id
     AND recovered_dep.is_critical = TRUE
    SET a.status = 'ACTIVE'
    WHERE a.status = 'DISABLED'
      AND NOT EXISTS (
          SELECT 1
          FROM agent_resources AS other_dep
          JOIN resources AS other_resource ON other_resource.resource_id = other_dep.resource_id
          WHERE other_dep.agent_id = a.agent_id
            AND other_dep.is_critical = TRUE
            AND other_resource.status = 'OFFLINE'
      );
END$$

DELIMITER ;
