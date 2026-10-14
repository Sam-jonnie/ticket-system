# Database design (ER diagram)

```mermaid
erDiagram
    users ||--o{ refresh_tokens : "has"
    users ||--o{ tickets : "opens (customer_id)"
    users |o--o{ tickets : "is assigned (assigned_agent_id)"
    ticket_categories ||--o{ tickets : "classifies"
    ticket_priorities ||--o{ tickets : "sets SLA for"
    tickets ||--o{ ticket_comments : "has"
    users ||--o{ ticket_comments : "writes"
    tickets ||--o{ ticket_attachments : "has"
    users ||--o{ ticket_attachments : "uploads"
    tickets ||--o{ ticket_status_history : "logs changes in"
    users |o--o{ ticket_status_history : "changed_by"
    users ||--o{ notifications : "receives"
    tickets |o--o{ notifications : "about"
    users |o--o{ audit_logs : "performs"

    users {
        uuid id PK
        string name
        string email UK
        string hashed_password
        user_role role "admin | agent | customer"
        bool is_active
        timestamptz created_at
        timestamptz updated_at
    }
    refresh_tokens {
        uuid id PK
        uuid user_id FK "CASCADE"
        string token UK
        timestamptz expires_at
        bool is_revoked
        timestamptz created_at
        timestamptz updated_at
    }
    ticket_categories {
        uuid id PK
        string name UK
        text description
        bool is_active
        timestamptz created_at
        timestamptz updated_at
    }
    ticket_priorities {
        uuid id PK
        ticket_priority name UK "low | medium | high | critical"
        int sla_hours
    }
    tickets {
        uuid id PK
        string ticket_number UK "TKT-00001"
        string title
        text description
        ticket_status status "open | in_progress | resolved | closed"
        uuid customer_id FK "RESTRICT"
        uuid assigned_agent_id FK "SET NULL"
        uuid category_id FK "RESTRICT"
        uuid priority_id FK "RESTRICT"
        timestamptz due_date
        timestamptz created_at
        timestamptz updated_at
    }
    ticket_comments {
        uuid id PK
        uuid ticket_id FK "CASCADE"
        uuid user_id FK "RESTRICT"
        text message
        timestamptz created_at
        timestamptz updated_at
    }
    ticket_attachments {
        uuid id PK
        uuid ticket_id FK "CASCADE"
        uuid uploaded_by_id FK "RESTRICT"
        string file_name
        string file_type "detected MIME type"
        bigint file_size
        string storage_path
        timestamptz created_at
        timestamptz updated_at
    }
    ticket_status_history {
        uuid id PK
        uuid ticket_id FK "CASCADE"
        uuid changed_by_id FK "SET NULL"
        ticket_status old_status
        ticket_status new_status
        uuid old_agent_id FK "SET NULL"
        uuid new_agent_id FK "SET NULL"
        string note
        timestamptz created_at
    }
    notifications {
        uuid id PK
        uuid user_id FK "CASCADE"
        uuid ticket_id FK "CASCADE, nullable"
        notification_type type
        string message
        bool is_read
        timestamptz created_at
        timestamptz updated_at
    }
    audit_logs {
        uuid id PK
        uuid user_id FK "SET NULL, nullable"
        audit_action action
        string entity
        string entity_id
        inet ip_address
        jsonb metadata
        timestamptz created_at
    }
```

**Delete rules in one sentence:** core ticket data (customer, category, priority, authors, uploaders) is protected with `RESTRICT`; things that only make sense alongside their parent (comments, attachments, history, notifications, refresh tokens) are removed with `CASCADE`; optional references (assigned agent, audit/history actor) become `NULL` with `SET NULL`.