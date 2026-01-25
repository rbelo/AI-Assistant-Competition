-- Dropping tables in reverse order of dependency to ensure no foreign key violations
DROP TABLE IF EXISTS student_prompt CASCADE;
DROP TABLE IF EXISTS playground_result CASCADE;
DROP TABLE IF EXISTS game_simulation_params CASCADE;
DROP TABLE IF EXISTS instructor_api_key CASCADE;
DROP TABLE IF EXISTS negotiation_chat CASCADE;
DROP TABLE IF EXISTS instructor CASCADE;
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

-- instructor table
CREATE TABLE instructor (
    user_id VARCHAR(50),                                                  -- Unique userID (university ID), cannot be null
    permission_level VARCHAR(20) NOT NULL,                                -- Permission level for the instructor, cannot be null
    PRIMARY KEY(user_id),                                                 -- Set username as the primary key
    FOREIGN KEY(user_id) REFERENCES user_(user_id)                        -- Foreign key linking to the username in the user table
);

-- instructor_api_key table
CREATE TABLE instructor_api_key (
    user_id VARCHAR(50),
    encrypted_key TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(user_id),
    FOREIGN KEY(user_id) REFERENCES user_(user_id) ON DELETE CASCADE
);

-- game table
CREATE TABLE game (
    game_id SERIAL,                                                       -- Unique identifier for each game, auto-incremented, not null
    available SMALLINT NOT NULL,                                          -- Indicates whether the negotiation chats are visible to students: 1 (visible), 0 (hidden).
    created_by VARCHAR(50) NOT NULL,                                      -- userID (university ID) of the instructor that created the game, cannot be null
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
    score_team1_role1 FLOAT,                                              -- Score of team 1 in a specific round with role1
    score_team2_role2 FLOAT,                                              -- Score of team 2 in a specific round with role2
    score_team1_role2 FLOAT,                                              -- Score of team 1 in a specific round with role2
    score_team2_role1 FLOAT,                                              -- Score of team 2 in a specific round with role1
    PRIMARY KEY(game_id, round_number, group1_class, group1_id, group2_class, group2_id),     -- Set game_id, round_number, group1_class, group1_id,  group2_class and group2_id as the composite primary keys
    FOREIGN KEY(game_id) REFERENCES game(game_id)                         -- Foreign key linking to the game_id in the game table
);

-- negotiation_chat table
CREATE TABLE negotiation_chat (
    game_id INT NOT NULL,
    round_number SMALLINT NOT NULL,
    group1_class CHAR(1) NOT NULL,
    group1_id SMALLINT NOT NULL,
    group2_class CHAR(1) NOT NULL,
    group2_id SMALLINT NOT NULL,
    transcript TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game_id, round_number, group1_class, group1_id, group2_class, group2_id),
    FOREIGN KEY (game_id) REFERENCES game(game_id) ON DELETE CASCADE
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

-- student_prompt table - stores student prompts
CREATE TABLE student_prompt (
    game_id INT NOT NULL,
    class VARCHAR(10) NOT NULL,
    group_id SMALLINT NOT NULL,
    prompt TEXT NOT NULL,                              -- Combined format with #_;:) delimiter
    submitted_by VARCHAR(50),                          -- user_id of the submitter
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game_id, class, group_id),
    FOREIGN KEY (game_id) REFERENCES game(game_id) ON DELETE CASCADE
);

-- metrics tables
CREATE TABLE page_visit (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255),
    page_name VARCHAR(255),
    entry_timestamp TIMESTAMP,
    exit_timestamp TIMESTAMP,
    duration_seconds FLOAT
);

CREATE TABLE game_interaction (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255),
    game_id INTEGER,
    game_type VARCHAR(50),
    completion_time FLOAT,
    score FLOAT,
    timestamp TIMESTAMP
);

CREATE TABLE prompt_metrics (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255),
    prompt_text TEXT,
    word_count INTEGER,
    character_count INTEGER,
    response_time FLOAT,
    timestamp TIMESTAMP
);

CREATE TABLE conversation_metrics (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255),
    conversation_id VARCHAR(255),
    total_exchanges INTEGER,
    conversation_duration FLOAT,
    timestamp TIMESTAMP
);

CREATE TABLE deal_metrics (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255),
    game_id INTEGER,
    negotiation_rounds INTEGER,
    deal_value FLOAT,
    deal_success BOOLEAN,
    timestamp TIMESTAMP
);

-- game_simulation_params table - stores simulation parameters for a game
CREATE TABLE game_simulation_params (
    game_id INT NOT NULL,
    model TEXT NOT NULL,
    conversation_order TEXT NOT NULL,
    starting_message TEXT NOT NULL,
    num_turns INT NOT NULL,
    negotiation_termination_message TEXT NOT NULL,
    summary_prompt TEXT NOT NULL,
    summary_termination_message TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game_id),
    FOREIGN KEY (game_id) REFERENCES game(game_id) ON DELETE CASCADE
);

-- playground_result table - stores playground negotiation transcripts
CREATE TABLE playground_result (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    class VARCHAR(10) NOT NULL,
    group_id INT NOT NULL,
    role1_name TEXT,
    role2_name TEXT,
    transcript TEXT NOT NULL,
    summary TEXT,
    deal_value FLOAT,
    score_role1 FLOAT,
    score_role2 FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
