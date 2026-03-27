CREATE TABLE IF NOT EXISTS claude_token_usage (
    id                    BIGINT AUTO_INCREMENT PRIMARY KEY,
    request_id            VARCHAR(64)   NULL,
    model                 VARCHAR(64)   NOT NULL,
    input_tokens          INT           NOT NULL DEFAULT 0,
    output_tokens         INT           NOT NULL DEFAULT 0,
    total_tokens          INT GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,
    cache_read_tokens     INT           NOT NULL DEFAULT 0,
    cache_creation_tokens INT           NOT NULL DEFAULT 0,
    input_cost            DECIMAL(12,6) NOT NULL DEFAULT 0,
    output_cost           DECIMAL(12,6) NOT NULL DEFAULT 0,
    total_cost            DECIMAL(12,6) GENERATED ALWAYS AS (input_cost + output_cost) STORED,
    task_label            VARCHAR(128)  NULL,
    project               VARCHAR(128)  NULL,
    method                VARCHAR(16)   NOT NULL COMMENT 'create or stream',
    duration_ms           INT           NULL,
    created_at            TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_model (model),
    INDEX idx_task_label (task_label),
    INDEX idx_project (project),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
