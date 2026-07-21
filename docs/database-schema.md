# Database Schema

erDiagram
User ||--o{ License : has
User ||--o{ Notification : receives
User ||--o{ AuditLog : performs
User ||--o{ EmailLog : receives
License ||--o{ LicenseAudit : has
License ||--o{ Notification : triggers

    User {
        uuid id PK
        string email UK
        string first_name
        string last_name
        string role
        string phone_number
        string employee_id UK
        boolean is_active
        datetime date_joined
        datetime last_updated
    }

    License {
        uuid id PK
        uuid agent_id FK
        string license_number UK
        date issue_date
        date expiry_date
        string certificate_file
        string status
        boolean is_verified
        uuid verified_by FK
        datetime verification_date
        text notes
        boolean reminder_30_sent
        boolean reminder_15_sent
        boolean reminder_7_sent
        datetime created_at
        datetime updated_at
    }

    LicenseAudit {
        uuid id PK
        uuid license_id FK
        string action
        uuid performed_by FK
        json changes
        text notes
        datetime created_at
    }

    Notification {
        uuid id PK
        uuid user_id FK
        string type
        string priority
        string title
        text message
        boolean is_read
        datetime read_at
        json metadata
        datetime created_at
    }

    EmailLog {
        uuid id PK
        string recipient
        string subject
        string template_name
        string status
        text error_message
        datetime sent_at
        datetime created_at
        json metadata
    }

    AuditLog {
        uuid id PK
        uuid user_id FK
        string action
        string resource_type
        string resource_id
        ip_address ip_address
        text user_agent
        json details
        datetime created_at
    }
