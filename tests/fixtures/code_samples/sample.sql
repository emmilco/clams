-- Sample SQL code for testing code parsing

-- Users table
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE
);

-- Orders view
CREATE VIEW user_orders AS
SELECT u.name, COUNT(o.id) as order_count
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
GROUP BY u.id;

-- Get user by email
CREATE FUNCTION get_user_by_email(p_email TEXT)
RETURNS TABLE(id INTEGER, name TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT id, name FROM users WHERE email = p_email;
END;
$$ LANGUAGE plpgsql;
