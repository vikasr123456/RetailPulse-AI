-- Run while connected to the retailpulse database.
SELECT current_database() AS database_name, current_user AS connected_user, version();

SELECT datname, pg_size_pretty(pg_database_size(datname)) AS size
FROM pg_database
WHERE datname = 'retailpulse';

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

SELECT
    (SELECT count(*) FROM products) AS products,
    (SELECT count(*) FROM sales) AS sales,
    (SELECT count(*) FROM users) AS users,
    (SELECT count(*) FROM stores) AS stores;
