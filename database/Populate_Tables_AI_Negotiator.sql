----------------------------------------------------------------------------------------------------------------------------------------------
---------------------------------------------------------- INSERT USERS ----------------------------------------------------------------------
----------------------------------------------------------------------------------------------------------------------------------------------

-- Inserting Ricardo Almeida (for testing)
INSERT INTO user_ (user_id, email, password, group_id, academic_year, class) 
VALUES ('nova199317', 'ricardo.almeida2210@gmail.com', '<hashed_password_for_ricardo>', 0, 2024, 'A');

-- Inserting Carolina Paiva (for testing)
INSERT INTO user_ (user_id, email, password, group_id, academic_year, class) 
VALUES ('nova199318', 'carolinapaivafifi@gmail.com', '<hashed_password_for_carolina>', 0, 2024, 'A');

-- Inserting António Almeida (for testing)
INSERT INTO user_ (user_id, email, password, group_id, academic_year, class) 
VALUES ('nova199319', 'antonio.c.almeida@tecnico.ulisboa.pt', '<hashed_password_for_antonio>', 0, 2024, 'A');

-- Inserting Martim Penim (for testing)
INSERT INTO user_ (user_id, email, password, group_id, academic_year, class) 
VALUES ('nova199320', 'martim.penim@tecnico.ulisboa.pt', '<hashed_password_for_martim>', 0, 2024, 'A');

-- Inserting Rodrigo Belo
INSERT INTO user_ (user_id, email, password, group_id, academic_year, class)
VALUES ('nova199032', 'rodrigo.belo@novasbe.pt', '<hashed_password_for_rodrigo>', 0, 2008, 'B');

-- Inserting Lénia Mestrinho
INSERT INTO user_ (user_id, email, password, group_id, academic_year, class)
VALUES ('nova196331', 'lenia.mestrinho@novasbe.pt', '<hashed_password_for_lenia>', 0, 2000, 'A');

----------------------------------------------------------------------------------------------------------------------------------------------
---------------------------------------------- INSERT PROFESSORS -----------------------------------------------------------------------------
----------------------------------------------------------------------------------------------------------------------------------------------

-- Inserting Ricardo Almeida into professor's table (for testing)
INSERT INTO professor (user_id, permission_level)
VALUES ('nova199317', 'regular');

-- Inserting Carolina Paiva into professor's table (for testing)
INSERT INTO professor (user_id, permission_level)
VALUES ('nova199318', 'regular');

-- Inserting António Almeida into professor's table (for testing)
INSERT INTO professor (user_id, permission_level)
VALUES ('nova199319', 'regular');

-- Inserting Martim Penim into professor's table (for testing)
INSERT INTO professor (user_id, permission_level) 
VALUES ('nova199320', 'regular');

-- Inserting Rodrigo Belo into professor's table
INSERT INTO professor (user_id, permission_level) 
VALUES ('nova199032', 'master');

-- Inserting Lénia Mestrinho into professor's table
INSERT INTO professor (user_id, permission_level) 
VALUES ('nova196331', 'regular');

----------------------------------------------------------------------------------------------------------------------------------------------
---------------------------------------------- INSERT GAME MODES -----------------------------------------------------------------------------
----------------------------------------------------------------------------------------------------------------------------------------------

-- Add game modes
INSERT INTO game_modes (mode_name, description) 
VALUES 
    ('zero_sum', 'Configuration for zero sum games'),
    ('prisoners_dilemma', 'Configuration for prisoners dilemma games');