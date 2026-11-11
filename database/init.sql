-- Create tables
CREATE TABLE IF NOT EXISTS urls (
    id SERIAL PRIMARY KEY,
    original_url TEXT NOT NULL,
    short_code VARCHAR(10) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    click_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS clicks (
    id SERIAL PRIMARY KEY,
    url_id INTEGER REFERENCES urls(id) ON DELETE CASCADE,
    clicked_at TIMESTAMP DEFAULT NOW(),
    ip_address VARCHAR(45),
    user_agent TEXT,
    referrer TEXT
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_short_code ON urls(short_code);
CREATE INDEX IF NOT EXISTS idx_created_at ON urls(created_at);
CREATE INDEX IF NOT EXISTS idx_url_id ON clicks(url_id);
CREATE INDEX IF NOT EXISTS idx_clicked_at ON clicks(clicked_at);

-- Insert sample data (optional)
INSERT INTO urls (original_url, short_code, created_at) VALUES
    ('https://www.github.com', 'github', NOW()),
    ('https://www.google.com', 'google', NOW())
ON CONFLICT (short_code) DO NOTHING;
