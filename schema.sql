-- FilePortal database schema (MySQL 8 / InnoDB, utf8mb4).
-- The application runs this file automatically on startup (it is idempotent),
-- but it can also be applied manually:  mysql -u root -p fileportal < schema.sql

CREATE TABLE IF NOT EXISTS users (
    id            INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    name          VARCHAR(100)  NOT NULL,
    age           TINYINT UNSIGNED NOT NULL,
    address       VARCHAR(255)  NOT NULL,
    email         VARCHAR(255)  NOT NULL,
    mobile        VARCHAR(20)   NOT NULL,
    password_hash VARCHAR(255)  NOT NULL,          -- salted hash, never plain text
    created_at    TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS uploaded_files (
    id                INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    user_id           INT UNSIGNED  NOT NULL,
    slot              TINYINT UNSIGNED NOT NULL,    -- 1 = "Upload File 1", 2 = "Upload File 2"
    original_filename VARCHAR(255)  NOT NULL,       -- name on the user's computer
    stored_filename   VARCHAR(255)  NOT NULL,       -- name on server disk (contains the user's name)
    file_type         VARCHAR(10)   NOT NULL,       -- PDF, PNG or JPEG
    file_size         INT UNSIGNED  NOT NULL,       -- bytes
    uploaded_at       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_files_stored (stored_filename),
    KEY idx_files_user (user_id, uploaded_at),
    CONSTRAINT fk_files_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
