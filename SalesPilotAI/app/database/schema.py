"""数据库初始结构。所有时间戳均以 UTC ISO-8601 文本保存。"""

KNOWLEDGE_SEARCH_SCHEMA = r"""
CREATE INDEX IF NOT EXISTS idx_knowledge_category
    ON knowledge_documents(category, imported_at DESC);

DROP TRIGGER IF EXISTS knowledge_fts_insert;
DROP TRIGGER IF EXISTS knowledge_fts_delete;
DROP TRIGGER IF EXISTS knowledge_fts_update;
DROP TABLE IF EXISTS knowledge_search;

CREATE VIRTUAL TABLE knowledge_search USING fts5(
    file_name,
    title,
    category,
    content,
    content='knowledge_documents',
    content_rowid='id',
    tokenize='trigram'
);

INSERT INTO knowledge_search(rowid, file_name, title, category, content)
SELECT id, file_name, coalesce(title, ''), coalesce(category, ''), content
FROM knowledge_documents;

CREATE TRIGGER IF NOT EXISTS knowledge_documents_fts_insert
AFTER INSERT ON knowledge_documents BEGIN
    INSERT INTO knowledge_search(rowid, file_name, title, category, content)
    VALUES (
        new.id, new.file_name, coalesce(new.title, ''),
        coalesce(new.category, ''), new.content
    );
END;

CREATE TRIGGER IF NOT EXISTS knowledge_documents_fts_delete
AFTER DELETE ON knowledge_documents BEGIN
    INSERT INTO knowledge_search(
        knowledge_search, rowid, file_name, title, category, content
    ) VALUES (
        'delete', old.id, old.file_name, coalesce(old.title, ''),
        coalesce(old.category, ''), old.content
    );
END;

CREATE TRIGGER IF NOT EXISTS knowledge_documents_fts_update
AFTER UPDATE ON knowledge_documents BEGIN
    INSERT INTO knowledge_search(
        knowledge_search, rowid, file_name, title, category, content
    ) VALUES (
        'delete', old.id, old.file_name, coalesce(old.title, ''),
        coalesce(old.category, ''), old.content
    );
    INSERT INTO knowledge_search(rowid, file_name, title, category, content)
    VALUES (
        new.id, new.file_name, coalesce(new.title, ''),
        coalesce(new.category, ''), new.content
    );
END;
"""

INITIAL_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS database_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    company_name TEXT,
    country TEXT,
    contact_info TEXT,
    whatsapp_number TEXT,
    email TEXT,
    website TEXT,
    customer_type TEXT,
    interested_products TEXT,
    expected_quantity TEXT,
    target_price TEXT,
    historical_quotes TEXT,
    purchase_history TEXT,
    sales_stage TEXT NOT NULL DEFAULT 'New Lead',
    intent_score INTEGER NOT NULL DEFAULT 0 CHECK (intent_score BETWEEN 0 AND 100),
    core_concerns TEXT,
    notes TEXT,
    first_contact_at TEXT,
    last_contact_at TEXT,
    next_followup_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    title TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    started_at TEXT,
    last_message_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    sender_type TEXT NOT NULL DEFAULT 'unknown'
        CHECK (sender_type IN ('customer', 'sales', 'unknown')),
    content TEXT NOT NULL,
    message_timestamp TEXT,
    sequence_number INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'manual',
    recognized_at TEXT,
    recognition_confidence REAL CHECK (
        recognition_confidence IS NULL OR recognition_confidence BETWEEN 0.0 AND 1.0
    ),
    may_be_incomplete INTEGER NOT NULL DEFAULT 0 CHECK (may_be_incomplete IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    conversation_id INTEGER,
    model TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'completed', 'failed')),
    latest_message_translation TEXT,
    customer_intent TEXT,
    customer_intent_explanation TEXT,
    customer_emotion TEXT,
    purchase_requirements_json TEXT,
    purchase_intent_score INTEGER CHECK (
        purchase_intent_score IS NULL OR purchase_intent_score BETWEEN 0 AND 100
    ),
    score_evidence_json TEXT,
    confidence REAL CHECK (confidence IS NULL OR confidence BETWEEN 0.0 AND 1.0),
    sales_stage TEXT,
    customer_concerns_json TEXT,
    price_sensitivity TEXT,
    communication_risks_json TEXT,
    opportunities_json TEXT,
    recommended_strategy TEXT,
    next_questions_json TEXT,
    followup_required INTEGER NOT NULL DEFAULT 0 CHECK (followup_required IN (0, 1)),
    followup_suggestion TEXT,
    unknown_information_json TEXT,
    raw_response TEXT,
    error_message TEXT,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS reply_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER NOT NULL,
    type TEXT NOT NULL CHECK (
        type IN ('professional', 'sales_driven', 'relationship_building')
    ),
    english TEXT NOT NULL,
    chinese TEXT NOT NULL,
    strategy TEXT NOT NULL,
    use_case TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE,
    UNIQUE (analysis_id, type)
);

CREATE TABLE IF NOT EXISTS customer_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual'
        CHECK (source IN ('manual', 'customer_confirmed', 'ai_suggested')),
    status TEXT NOT NULL DEFAULT 'confirmed'
        CHECK (status IN ('pending', 'confirmed', 'rejected')),
    confirmed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    model TEXT,
    category TEXT,
    specifications_json TEXT,
    features TEXT,
    price TEXT,
    moq TEXT,
    packaging TEXT,
    lead_time TEXT,
    certifications TEXT,
    payment_terms TEXT,
    logistics_policy TEXT,
    after_sales_policy TEXT,
    oem_odm_terms TEXT,
    faq TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS knowledge_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT NOT NULL,
    title TEXT,
    category TEXT,
    content TEXT NOT NULL DEFAULT '',
    checksum TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'indexed', 'failed')),
    error_message TEXT,
    imported_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS followups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    analysis_id INTEGER,
    due_at TEXT NOT NULL,
    reason TEXT,
    priority TEXT NOT NULL DEFAULT 'medium'
        CHECK (priority IN ('low', 'medium', 'high')),
    content TEXT NOT NULL,
    result TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'completed', 'cancelled')),
    completed_at TEXT,
    cancelled_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS api_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL DEFAULT 'deepseek',
    model TEXT NOT NULL,
    endpoint TEXT,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK (status IN ('success', 'failed')),
    error_type TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_customers_country ON customers(country);
CREATE INDEX IF NOT EXISTS idx_customers_stage ON customers(sales_stage);
CREATE INDEX IF NOT EXISTS idx_customers_intent ON customers(intent_score DESC);
CREATE INDEX IF NOT EXISTS idx_customers_last_contact ON customers(last_contact_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_customer ON conversations(customer_id, last_message_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, sequence_number);
CREATE INDEX IF NOT EXISTS idx_analyses_customer ON analyses(customer_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analyses_created ON analyses(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_customer ON customer_memories(customer_id, status);
CREATE INDEX IF NOT EXISTS idx_products_name_model ON products(name, model);
CREATE INDEX IF NOT EXISTS idx_knowledge_product ON knowledge_documents(product_id, category);
CREATE INDEX IF NOT EXISTS idx_followups_due ON followups(status, due_at);
CREATE INDEX IF NOT EXISTS idx_followups_customer ON followups(customer_id, status, due_at);
CREATE INDEX IF NOT EXISTS idx_api_usage_created ON api_usage(created_at DESC);

CREATE VIRTUAL TABLE IF NOT EXISTS customer_search USING fts5(
    name,
    company_name,
    whatsapp_number,
    email,
    interested_products,
    content='customers',
    content_rowid='id',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS customers_fts_insert AFTER INSERT ON customers BEGIN
    INSERT INTO customer_search(
        rowid, name, company_name, whatsapp_number, email, interested_products
    ) VALUES (
        new.id, new.name, new.company_name, new.whatsapp_number, new.email,
        new.interested_products
    );
END;

CREATE TRIGGER IF NOT EXISTS customers_fts_delete AFTER DELETE ON customers BEGIN
    INSERT INTO customer_search(
        customer_search, rowid, name, company_name, whatsapp_number, email,
        interested_products
    ) VALUES (
        'delete', old.id, old.name, old.company_name, old.whatsapp_number, old.email,
        old.interested_products
    );
END;

CREATE TRIGGER IF NOT EXISTS customers_fts_update AFTER UPDATE ON customers BEGIN
    INSERT INTO customer_search(
        customer_search, rowid, name, company_name, whatsapp_number, email,
        interested_products
    ) VALUES (
        'delete', old.id, old.name, old.company_name, old.whatsapp_number, old.email,
        old.interested_products
    );
    INSERT INTO customer_search(
        rowid, name, company_name, whatsapp_number, email, interested_products
    ) VALUES (
        new.id, new.name, new.company_name, new.whatsapp_number, new.email,
        new.interested_products
    );
END;

CREATE VIRTUAL TABLE IF NOT EXISTS message_search USING fts5(
    content,
    content='messages',
    content_rowid='id',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS messages_fts_insert AFTER INSERT ON messages BEGIN
    INSERT INTO message_search(rowid, content) VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS messages_fts_delete AFTER DELETE ON messages BEGIN
    INSERT INTO message_search(message_search, rowid, content)
    VALUES ('delete', old.id, old.content);
END;

CREATE TRIGGER IF NOT EXISTS messages_fts_update AFTER UPDATE ON messages BEGIN
    INSERT INTO message_search(message_search, rowid, content)
    VALUES ('delete', old.id, old.content);
    INSERT INTO message_search(rowid, content) VALUES (new.id, new.content);
END;

CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_search USING fts5(
    title,
    category,
    content,
    content='knowledge_documents',
    content_rowid='id',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS knowledge_fts_insert AFTER INSERT ON knowledge_documents BEGIN
    INSERT INTO knowledge_search(rowid, title, category, content)
    VALUES (new.id, new.title, new.category, new.content);
END;

CREATE TRIGGER IF NOT EXISTS knowledge_fts_delete AFTER DELETE ON knowledge_documents BEGIN
    INSERT INTO knowledge_search(knowledge_search, rowid, title, category, content)
    VALUES ('delete', old.id, old.title, old.category, old.content);
END;

CREATE TRIGGER IF NOT EXISTS knowledge_fts_update AFTER UPDATE ON knowledge_documents BEGIN
    INSERT INTO knowledge_search(knowledge_search, rowid, title, category, content)
    VALUES ('delete', old.id, old.title, old.category, old.content);
    INSERT INTO knowledge_search(rowid, title, category, content)
    VALUES (new.id, new.title, new.category, new.content);
END;
"""
