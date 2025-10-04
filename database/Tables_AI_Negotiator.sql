-- Dropping tables in reverse order of dependency to ensure no foreign key violations                                 
DROP TABLE IF EXISTS professor CASCADE;
DROP TABLE IF EXISTS plays CASCADE;                              
DROP TABLE IF EXISTS user_ CASCADE;
DROP TABLE IF EXISTS round CASCADE;
DROP TABLE IF EXISTS game CASCADE;
DROP TABLE IF EXISTS group_values CASCADE;
DROP TABLE IF EXISTS game_modes CASCADE;
DROP TABLE IF EXISTS zero_sum_game_config CASCADE;
DROP TABLE IF EXISTS prisoners_dilemma_config CASCADE;


-- user table
CREATE TABLE user_ (
    user_id VARCHAR(50),                                                  -- Unique userID (university ID), cannot be null
    email VARCHAR(100) NOT NULL,                                          -- Unique email address, cannot be null
    password VARCHAR(100) NOT NULL,                                       -- Hashed password for secure login, cannot be null
    group_id SMALLINT NOT NULL,                                           -- The groupID of the student, cannot be null
    academic_year SMALLINT NOT NULL,                                      -- Academic year of the user, cannot be null
    class CHAR(1) NOT NULL,                                               -- Represents the class of the user, such as 'A' or 'B', cannot be null
    timestamp_user TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                   -- Timestamp of account creation, defaults to the current time
    PRIMARY KEY(user_id),                                                 -- Set username as the primary key
    UNIQUE(email)                                                         -- Enforce unique constraint on email
);

-- professor table
CREATE TABLE professor (
    user_id VARCHAR(50),                                                  -- Unique userID (university ID), cannot be null
    permission_level VARCHAR(20) NOT NULL,                                -- Permission level for the professor, cannot be null
    PRIMARY KEY(user_id),                                                 -- Set username as the primary key
    FOREIGN KEY(user_id) REFERENCES user_(user_id)                        -- Foreign key linking to the username in the user table
);

-- game table
CREATE TABLE game (
    game_id SERIAL,                                                       -- Unique identifier for each game, auto-incremented, not null
    available SMALLINT NOT NULL,                                          -- Indicates whether the negotiation chats are visible to students: 1 (visible), 0 (hidden).
    created_by VARCHAR(50) NOT NULL,                                      -- userID (university ID) of the professor that created the game, cannot be null
    game_name VARCHAR(100) NOT NULL,                                      -- Name of the game, cannot be null
    number_of_rounds SMALLINT NOT NULL,                                   -- Number of rounds in the game, cannot be null
    name_roles VARCHAR(50) NOT NULL,                                      -- Names of the roles in the game, cannot be null
    game_academic_year SMALLINT NOT NULL,                                 -- Academic year related to the game, cannot be null
    game_class CHAR(1) NOT NULL,                                          -- Represents the class related to the game, such as 'A', 'B' or '_' (case where I want to consider all the classes in a certain academic year), cannot be null
    password VARCHAR(100) NOT NULL,                                       -- Hashed password to enter the game, cannot be null 
    timestamp_game_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,          -- Timestamp of game creation, defaults to the current time
    timestamp_submission_deadline TIMESTAMP DEFAULT CURRENT_TIMESTAMP,    -- Timestamp of the submission deadline, defaults to the current time
    explanation TEXT,                                                     -- Explanation of the game rules and objectives
    PRIMARY KEY(game_id)                                                  -- Set game_id as the primary key
    -- Every game must exist in the table 'plays'
    -- Every game must exist in the table 'contains'
);

-- group_values table
CREATE TABLE group_values (
    game_id INT NOT NULL,
    class VARCHAR(10) NOT NULL,
    group_id INT NOT NULL,
    minimizer_value FLOAT NOT NULL,
    maximizer_value FLOAT NOT NULL,
    PRIMARY KEY (game_id, class, group_id),
    FOREIGN KEY (game_id) REFERENCES game(game_id) ON DELETE CASCADE
);

-- plays table
CREATE TABLE plays (
    user_id VARCHAR(50),                                                  -- Unique userID (university ID), cannot be null
    game_id SERIAL,                                                       -- Unique identifier for each game, auto-incremented, not null
    PRIMARY KEY(user_id, game_id),                                        -- Set userID and game_id as a composite primary key
    FOREIGN KEY(user_Id) REFERENCES user_(user_id),                       -- Foreign key linking to the userID in the user table
    FOREIGN KEY(game_id) REFERENCES game(game_id)                         -- Foreign key linking to the game_id in the game table
);

-- round table
CREATE TABLE round (
    game_id SERIAL,                                                       -- Foreign key linking to the game_id in the game table
    round_number SMALLINT NOT NULL,                                       -- Number of the round in the game, cannot be null
    group1_class CHAR(1) NOT NULL, 					                      -- Class of the first group participating in the round, cannot be null
    group1_id SMALLINT NOT NULL,                                          -- ID of the first group participating in the round, cannot be null
    group2_class CHAR(1) NOT NULL,                                        -- Class of the second group participating in the round, cannot be null
    group2_id SMALLINT NOT NULL,                                          -- ID of the second group participating in the round, cannot be null
    score_team1_role1 FLOAT NOT NULL,                                     -- Score of team 1 in a specific round with role1, cannot be null
    score_team2_role2 FLOAT NOT NULL,                                     -- Score of team 2 in a specific round with role2, cannot be null
    score_team1_role2 FLOAT NOT NULL,                                     -- Score of team 1 in a specific round with role2, cannot be null
    score_team2_role1 FLOAT NOT NULL,                                     -- Score of team 2 in a specific round with role1, cannot be null
    PRIMARY KEY(game_id, round_number, group1_class, group1_id, group2_class, group2_id),     -- Set game_id, round_number, group1_class, group1_id,  group2_class and group2_id as the composite primary keys
    FOREIGN KEY(game_id) REFERENCES game(game_id)                         -- Foreign key linking to the game_id in the game table
);


-- Create a table for game modes
CREATE TABLE game_modes (
    mode_id SERIAL PRIMARY KEY,
    mode_name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT
);

-- Add a foreign key to the game table to reference game modes
ALTER TABLE game
ADD COLUMN mode_id INT,
ADD CONSTRAINT fk_game_mode FOREIGN KEY (mode_id) REFERENCES game_modes(mode_id);

-- Add a table for Zero-Sum game-specific configurations
CREATE TABLE zero_sum_game_config (
    config_id SERIAL PRIMARY KEY,
    game_id INT NOT NULL,
    minimizer_role_name VARCHAR(50),
    maximizer_role_name VARCHAR(50),
    min_minimizer_value INT,
    max_minimizer_value INT,
    min_maximizer_value INT,
    max_maximizer_value INT,
    FOREIGN KEY (game_id) REFERENCES game(game_id) ON DELETE CASCADE
);

-- Add a table for Prisoner's Dilemma game-specific configurations
CREATE TABLE prisoners_dilemma_config (
    config_id SERIAL PRIMARY KEY,
    game_id INT NOT NULL,
    payoff_matrix JSONB NOT NULL,
    FOREIGN KEY (game_id) REFERENCES game(game_id) ON DELETE CASCADE
);