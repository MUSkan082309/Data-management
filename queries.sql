-- name: null_or_empty_emails
SELECT id FROM users WHERE email IS NULL OR email = '';

-- name: duplicate_emails
SELECT email, COUNT(*) AS cnt FROM users WHERE email <> '' GROUP BY email HAVING COUNT(*) > 1;

-- name: age_out_of_range
SELECT id, age FROM users WHERE age < 0 OR age > 120;