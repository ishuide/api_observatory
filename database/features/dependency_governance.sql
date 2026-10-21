USE ai_agent_registry;

-- Dependency governance feature: reject unsafe bindings and maintain an audit trail.
DROP TRIGGER IF EXISTS trg_prevent_offline_resource_binding;
DROP TRIGGER IF EXISTS trg_agent_resource_insert_audit;
DROP TRIGGER IF EXISTS trg_agent_resource_delete_audit;

DELIMITER $$

CREATE TRIGGER trg_prevent_offline_resource_binding
BEFORE INSERT ON agent_resources
FOR EACH ROW
BEGIN
    DECLARE current_resource_status VARCHAR(20);

    SELECT status INTO current_resource_status
    FROM resources
    WHERE resource_id = NEW.resource_id;

    IF current_resource_status = 'OFFLINE' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Cannot attach an agent to an offline resource';
    END IF;
END$$

CREATE TRIGGER trg_agent_resource_insert_audit
AFTER INSERT ON agent_resources
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, operation, record_id, changed_by, change_details)
    VALUES (
        'agent_resources', 'DEPENDENCY_ADDED', NEW.agent_id, CURRENT_USER(),
        JSON_OBJECT('agent_id', NEW.agent_id, 'resource_id', NEW.resource_id,
                    'dependency_type', NEW.dependency_type, 'is_critical', NEW.is_critical)
    );
END$$

CREATE TRIGGER trg_agent_resource_delete_audit
AFTER DELETE ON agent_resources
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, operation, record_id, changed_by, change_details)
    VALUES (
        'agent_resources', 'DEPENDENCY_REMOVED', OLD.agent_id, CURRENT_USER(),
        JSON_OBJECT('agent_id', OLD.agent_id, 'resource_id', OLD.resource_id,
                    'dependency_type', OLD.dependency_type, 'is_critical', OLD.is_critical)
    );
END$$

DELIMITER ;
