USE ai_agent_registry;

CREATE TABLE IF NOT EXISTS app_users (
    user_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    username VARCHAR(80) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP NULL,
    PRIMARY KEY (user_id),
    UNIQUE KEY uq_app_users_username (username)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS app_roles (
    role_id SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    role_name VARCHAR(40) NOT NULL,
    description VARCHAR(255) NOT NULL,
    PRIMARY KEY (role_id),
    UNIQUE KEY uq_app_roles_name (role_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS app_permissions (
    permission_id SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    permission_key VARCHAR(80) NOT NULL,
    description VARCHAR(255) NOT NULL,
    PRIMARY KEY (permission_id),
    UNIQUE KEY uq_app_permissions_key (permission_key)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS app_user_roles (
    user_id INT UNSIGNED NOT NULL,
    role_id SMALLINT UNSIGNED NOT NULL,
    PRIMARY KEY (user_id, role_id),
    CONSTRAINT fk_app_user_roles_user FOREIGN KEY (user_id)
        REFERENCES app_users (user_id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_app_user_roles_role FOREIGN KEY (role_id)
        REFERENCES app_roles (role_id) ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS app_role_permissions (
    role_id SMALLINT UNSIGNED NOT NULL,
    permission_id SMALLINT UNSIGNED NOT NULL,
    PRIMARY KEY (role_id, permission_id),
    CONSTRAINT fk_app_role_permissions_role FOREIGN KEY (role_id)
        REFERENCES app_roles (role_id) ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_app_role_permissions_permission FOREIGN KEY (permission_id)
        REFERENCES app_permissions (permission_id) ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

INSERT INTO app_roles (role_name, description) VALUES
    ('Admin', 'Manage users and perform all registry operations'),
    ('Operator', 'Manage agents, resources, dependencies, imports, and health actions'),
    ('Viewer', 'Read registry, impact analysis, and audit history')
ON DUPLICATE KEY UPDATE description = VALUES(description);

INSERT INTO app_permissions (permission_key, description) VALUES
    ('registry.read', 'View registry data, graph, and impact analysis'),
    ('audit.read', 'View database audit history'),
    ('agents.manage', 'Create, edit, delete, and onboard agents'),
    ('resources.manage', 'Create, edit, and delete resources'),
    ('dependencies.manage', 'Create and remove agent-resource dependencies'),
    ('resources.health', 'Deactivate and recover resources'),
    ('imports.manage', 'Import company architecture JSON'),
    ('users.manage', 'Create users, assign roles, and deactivate accounts')
ON DUPLICATE KEY UPDATE description = VALUES(description);

INSERT IGNORE INTO app_role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM app_roles AS r
CROSS JOIN app_permissions AS p
WHERE r.role_name = 'Admin';

INSERT IGNORE INTO app_role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM app_roles AS r
JOIN app_permissions AS p
  ON p.permission_key IN (
      'registry.read', 'audit.read', 'agents.manage', 'resources.manage',
      'dependencies.manage', 'resources.health', 'imports.manage'
  )
WHERE r.role_name = 'Operator';

INSERT IGNORE INTO app_role_permissions (role_id, permission_id)
SELECT r.role_id, p.permission_id
FROM app_roles AS r
JOIN app_permissions AS p
  ON p.permission_key IN ('registry.read', 'audit.read')
WHERE r.role_name = 'Viewer';
