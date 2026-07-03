-- Schema do login multiusuário do dashboard SSA Monitor Processos.
-- Rodar uma vez no banco (mesma base do restante do sistema):
--   mysql -u ssa_user -p ssa_monitor_processos < deploy/schema_usuarios.sql

CREATE TABLE IF NOT EXISTS usuarios (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    nome                  VARCHAR(150) NOT NULL,
    email                 VARCHAR(150) NOT NULL UNIQUE,
    senha_hash            VARCHAR(255) NOT NULL,
    is_admin              BOOLEAN NOT NULL DEFAULT FALSE,
    ativo                 BOOLEAN NOT NULL DEFAULT TRUE,
    precisa_trocar_senha  BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em             DATETIME DEFAULT CURRENT_TIMESTAMP,
    ultimo_login          DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS sessoes (
    token       VARCHAR(64) PRIMARY KEY,
    usuario_id  INT NOT NULL,
    criado_em   DATETIME DEFAULT CURRENT_TIMESTAMP,
    expira_em   DATETIME NOT NULL,
    ip          VARCHAR(45),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS log_acessos (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id    INT NULL,
    email_tentado VARCHAR(150),
    sucesso       BOOLEAN NOT NULL,
    ip            VARCHAR(45),
    rota          VARCHAR(255),
    criado_em     DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_log_acessos_email_data ON log_acessos (email_tentado, criado_em);
CREATE INDEX idx_sessoes_expira ON sessoes (expira_em);
