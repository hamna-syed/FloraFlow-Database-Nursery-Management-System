USE floraflowdb;
SET SQL_SAFE_UPDATES = 0;
UPDATE Staff SET passwordHash = 'admin123' WHERE username = 'admin';
UPDATE Staff SET passwordHash = 'staff123' WHERE username != 'admin';
SET SQL_SAFE_UPDATES = 1;
COMMIT;
USE floraflowdb;
SELECT staffId, username, passwordHash FROM Staff;