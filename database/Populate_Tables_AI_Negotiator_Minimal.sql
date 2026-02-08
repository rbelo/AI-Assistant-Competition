----------------------------------------------------------------------------------------------------------------------------------------------
------------------------------------------------------ MINIMAL PRODUCTION/STAGING SEED ------------------------------------------------------
----------------------------------------------------------------------------------------------------------------------------------------------

-- This script expects psql variables:
--   :admin_email
--   :admin_password_hash
-- Use Makefile reset-production-db/reset-staging-db targets, which enforce these.
-- Password hash format is SHA-256 hex.

INSERT INTO user_ (user_id, email, password, group_id, academic_year, class)
VALUES
    ('admin', :'admin_email', :'admin_password_hash', 0, '0', 'ADMIN');

INSERT INTO instructor (user_id, permission_level)
VALUES
    ('admin', 'admin');

-- Pre-seed supported game modes (the app can also create them on demand).
INSERT INTO game_modes (mode_name, description)
VALUES
    ('zero_sum', 'Configuration for zero sum games'),
    ('prisoners_dilemma', 'Configuration for prisoners dilemma games');
