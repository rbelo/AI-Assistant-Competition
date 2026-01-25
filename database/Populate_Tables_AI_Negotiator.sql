----------------------------------------------------------------------------------------------------------------------------------------------
----------------------------------------------------------- INSERT USERS ----------------------------------------------------------------------
----------------------------------------------------------------------------------------------------------------------------------------------

-- Password hashes are SHA-256. Plaintext reference:
-- admin123 -> 240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9
-- instructor123 -> c1437a55f6e93b7049c4064af1b0920974e383a435283f5d0b0496ee4a8a47b5
-- student123 -> 703b0a3d6ad75b649a28adde7d83c6251da457549263bc7ff45ec709b0a8448b

-- Admin + instructors
INSERT INTO user_ (user_id, email, password, group_id, academic_year, class)
VALUES
    ('admin', 'admin@rodrigobelo.com', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', 0, 0, '_'),
    ('inst001', 'instructor1@example.com', 'c1437a55f6e93b7049c4064af1b0920974e383a435283f5d0b0496ee4a8a47b5', 0, 2049, 'T'),
    ('inst002', 'instructor2@example.com', 'c1437a55f6e93b7049c4064af1b0920974e383a435283f5d0b0496ee4a8a47b5', 0, 2049, 'U');

-- Students (class T)
INSERT INTO user_ (user_id, email, password, group_id, academic_year, class)
VALUES
    ('stud001', 'student1@example.com', '703b0a3d6ad75b649a28adde7d83c6251da457549263bc7ff45ec709b0a8448b', 1, 2049, 'T'),
    ('stud002', 'student2@example.com', '703b0a3d6ad75b649a28adde7d83c6251da457549263bc7ff45ec709b0a8448b', 2, 2049, 'T'),
    ('stud003', 'student3@example.com', '703b0a3d6ad75b649a28adde7d83c6251da457549263bc7ff45ec709b0a8448b', 3, 2049, 'T'),
    ('stud007', 'student@rodrigobelo.com', '703b0a3d6ad75b649a28adde7d83c6251da457549263bc7ff45ec709b0a8448b', 1, 2049, 'T');

-- Students (class U)
INSERT INTO user_ (user_id, email, password, group_id, academic_year, class)
VALUES
    ('stud004', 'student4@example.com', '703b0a3d6ad75b649a28adde7d83c6251da457549263bc7ff45ec709b0a8448b', 1, 2049, 'U'),
    ('stud005', 'student5@example.com', '703b0a3d6ad75b649a28adde7d83c6251da457549263bc7ff45ec709b0a8448b', 2, 2049, 'U'),
    ('stud006', 'student6@example.com', '703b0a3d6ad75b649a28adde7d83c6251da457549263bc7ff45ec709b0a8448b', 3, 2049, 'U');

----------------------------------------------------------------------------------------------------------------------------------------------
----------------------------------------------- INSERT INSTRUCTORS ----------------------------------------------------------------------------
----------------------------------------------------------------------------------------------------------------------------------------------

INSERT INTO instructor (user_id, permission_level)
VALUES
    ('admin', 'admin'),
    ('inst001', 'regular'),
    ('inst002', 'regular');

----------------------------------------------------------------------------------------------------------------------------------------------
----------------------------------------------- INSERT GAME MODES -----------------------------------------------------------------------------
----------------------------------------------------------------------------------------------------------------------------------------------

-- Add game modes
INSERT INTO game_modes (mode_name, description) 
VALUES 
    ('zero_sum', 'Configuration for zero sum games'),
    ('prisoners_dilemma', 'Configuration for prisoners dilemma games');

----------------------------------------------------------------------------------------------------------------------------------------------
----------------------------------------------------------- INSERT GAMES ----------------------------------------------------------------------
----------------------------------------------------------------------------------------------------------------------------------------------

INSERT INTO game (
    game_id, available, created_by, game_name, number_of_rounds, name_roles,
    game_academic_year, game_class, password, timestamp_game_creation,
    timestamp_submission_deadline, explanation, mode_id
)
VALUES
    (
        1, 0, 'inst001', 'Sample Zero Sum', 1, 'Buyer#_;:)Seller',
        2049, 'T', '1234', NOW(), NOW() + INTERVAL '7 days',
        'Negotiate the price of a refurbished laptop for a campus co-working space. Buyer has a strict budget; seller has limited inventory and a target margin.',
        (SELECT mode_id FROM game_modes WHERE mode_name = 'zero_sum')
    ),
    (
        2, 0, 'inst002', 'Sample Zero Sum', 1, 'Importer#_;:)Exporter',
        2049, 'U', '1234', NOW(), NOW() + INTERVAL '7 days',
        'Negotiate a quarterly contract for specialty coffee beans. Importer needs reliable delivery; exporter wants price stability and volume commitments.',
        (SELECT mode_id FROM game_modes WHERE mode_name = 'zero_sum')
    );

----------------------------------------------------------------------------------------------------------------------------------------------
--------------------------------------------------------- INSERT PLAYS -----------------------------------------------------------------------
----------------------------------------------------------------------------------------------------------------------------------------------

INSERT INTO plays (user_id, game_id)
VALUES
    ('stud001', 1),
    ('stud002', 1),
    ('stud003', 1),
    ('stud007', 1),
    ('stud004', 2),
    ('stud005', 2),
    ('stud006', 2);

----------------------------------------------------------------------------------------------------------------------------------------------
------------------------------------------------------ INSERT GAME PARAMETERS ----------------------------------------------------------------
----------------------------------------------------------------------------------------------------------------------------------------------

-- Parameters for game 1 (stored in group_values with class = 'params')
INSERT INTO group_values (game_id, class, group_id, minimizer_value, maximizer_value)
VALUES
    (1, 'params', 0, 10, 5),
    (1, 'params', 1, 30, 15);

-- Parameters for game 2
INSERT INTO group_values (game_id, class, group_id, minimizer_value, maximizer_value)
VALUES
    (2, 'params', 0, 20, 8),
    (2, 'params', 1, 40, 18);

----------------------------------------------------------------------------------------------------------------------------------------------
------------------------------------------------------ INSERT GROUP VALUES -------------------------------------------------------------------
----------------------------------------------------------------------------------------------------------------------------------------------

INSERT INTO group_values (game_id, class, group_id, minimizer_value, maximizer_value)
VALUES
    (1, 'T', 1, 12, 7),
    (1, 'T', 2, 18, 9),
    (1, 'T', 3, 22, 11),
    (2, 'U', 1, 25, 10),
    (2, 'U', 2, 28, 12),
    (2, 'U', 3, 32, 14);

----------------------------------------------------------------------------------------------------------------------------------------------
------------------------------------------------------ INSERT STUDENT PROMPTS ----------------------------------------------------------------
----------------------------------------------------------------------------------------------------------------------------------------------

INSERT INTO student_prompt (game_id, class, group_id, prompt, submitted_by)
VALUES
    (
        1, 'T', 1,
        'You are the buyer. Your reservation value is 12. Aim for a fair deal but try to stay below 10.\n\n#_;:)\n\nYou are the seller. Your reservation value is 7. Try to close above 12.',
        'stud001'
    ),
    (
        1, 'T', 2,
        'Buyer role: keep the offer under 15 and open with 8.\n\n#_;:)\n\nSeller role: ask for 20 and do not go below 9.',
        'stud002'
    ),
    (
        1, 'T', 3,
        'Buyer: emphasize long-term partnership and stay under 14.\n\n#_;:)\n\nSeller: highlight warranty and hold above 11.',
        'stud003'
    ),
    (
        2, 'U', 1,
        'Importer: keep total contract under 25 and push for volume discounts.\n\n#_;:)\n\nExporter: target 35 and do not accept below 10.',
        'stud004'
    );
