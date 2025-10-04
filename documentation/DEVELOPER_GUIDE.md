# Developer Guide

This guide provides detailed information for developers and contributors to the AI Assistant Competition platform.

## Quick Links
- GitHub Repository: [https://github.com/rbelo/AI-Assistant-Competition](https://github.com/rbelo/AI-Assistant-Competition)
- Live Application: [https://ai-assistant-competition.streamlit.app/](https://ai-assistant-competition.streamlit.app/)

---

## Table of Contents
1. [Prerequisites](#1-prerequisites)
2. [Development Environment](#2-development-environment)
3. [Project Structure](#3-project-structure)
4. [Database Setup](#4-database-setup)
5. [Running the Application](#5-running-the-application)
6. [Testing & Quality Assurance](#6-testing--quality-assurance)
7. [Contributing](#7-contributing)

---

## 1. Prerequisites

- Python 3.11 (required, as specified in devcontainer)
- PostgreSQL 13+
- Node.js & npm
- Git
- Docker (optional, but recommended for consistent development environment)

### 1.1 Key Dependencies
The project requires several key Python packages:
- Streamlit 1.32.0+ (for the web interface)
- Psycopg2-binary (for PostgreSQL connection)
- PyJWT (for authentication)
- Streamlit-AgGrid (for data grid display)
- AutoGen (for agent automation)
- OpenAI (for AI model integration)
- Flask (for web services)
- Google API Client & Auth (for Google Drive integration)
- Pandas (for data manipulation)
- Matplotlib (for data visualization)
- Pytest (for testing)

A complete list of dependencies can be found in `streamlit/requirements.txt`.

---

## 2. Development Environment

The project provides multiple ways to set up your development environment:

- Using `environment.yml` for Conda environments
- Using `requirements.txt` for pip installations
- Using `.devcontainer` for VS Code development containers

Choose the method that best suits your workflow. All necessary dependencies and configurations are included in these files.

---

## 3. Database Setup

### 3.1 Database Schema

The database consists of the following main tables:

- `user_`: Stores user accounts and authentication information
- `professor`: Contains professor-specific permissions and settings
- `game`: Records game instances and configurations
- `group_values`: Stores group-specific values for games
- `plays`: Tracks which users are participating in which games
- `round`: Records round results and scores
- `game_modes`: Defines different types of games
- `zero_sum_game_config`: Configuration for zero-sum games
- `prisoners_dilemma_config`: Configuration for prisoner's dilemma games

For the complete schema definition, see `Tables_AI_Negotiator.sql`.

### 3.2 Initial Setup

1. Create Database:
   ```bash
   createdb ai_assistant_competition
   ```

2. Initialize Schema:
   ```bash
   psql -d ai_assistant_competition -f Tables_AI_Negotiator.sql
   ```

3. Load Sample Data (Optional):
   ```bash
   psql -d ai_assistant_competition -f Populate_Tables_AI_Negotiator.sql
   ```

4. Configure Connection:
   - Edit `streamlit/.streamlit/secrets.toml`:
     ```toml
     database = "postgresql://localhost/ai_assistant_competition"
     ```
   - Test connection:
     ```bash
     psql -d ai_assistant_competition -c "SELECT 'Connection successful' AS status;"
     ```

### 3.3 Data Management

1. User Management:
   - Professors can add students through the Control Panel's CSV upload feature (available at `/Control_Panel` page)
     - The CSV must follow this format:
     ```csv
     userID;email;groupID;academic year;class
     ```
   - Users can also be added directly via SQL queries:
     ```sql
     INSERT INTO user_ (user_id, email, password, group_id, academic_year, class) 
     VALUES ('user_id', 'email', 'hashed_password', group_id, academic_year, 'class');
     
     -- If the user is a professor, also add to professor table:
     INSERT INTO professor (user_id, permission_level)
     VALUES ('user_id', 'regular');
     ```

2. Viewing Data:
   ```bash
   # Connect to database
   psql -d ai_assistant_competition

   # List tables
   \dt

   # View users
   SELECT * FROM user_;

   # View professors
   SELECT * FROM professor;

   # View games
   SELECT * FROM game;
   ```

### 3.4 Backup & Recovery

1. Create Backup:
   ```bash
   pg_dump ai_assistant_competition > backup.sql
   ```

2. Restore from Backup:
   ```bash
   psql -d ai_assistant_competition < backup.sql
   ```

---

## 4. Running the Application

### 4.1 Development Mode
```bash
# Navigate to the streamlit directory and run the app
cd AI-Assistant-Competition/streamlit && streamlit run 0_Home.py
```

The application will be available at `http://localhost:8501`.

> **Note:** It's important to run the app from the streamlit directory to ensure proper access to the secrets.toml file located in the .streamlit directory.

### 4.2 Production Mode
```bash
# Build the application
streamlit build

# Run with production settings
streamlit run streamlit/0_Home.py --server.port=8501 --server.address=0.0.0.0
```

---

## 5. Testing & Quality Assurance

### 5.1 Running Tests

The project uses pytest for testing. To run the tests:

```bash
# Set PYTHONPATH to include project root (required for imports to work)
export PYTHONPATH=$PYTHONPATH:$(pwd)

# Run specific test file
pytest tests/unit_tests.py

# Run specific test function
pytest tests/unit_tests.py::test_database_connection
```

> **Note:** Setting PYTHONPATH is required because the tests need to import modules from the `streamlit` directory. The test file automatically adds the project root to the Python path, but it's good practice to set it in your environment as well.

### 5.2 Test Categories

The test suite includes tests for:

1. **Authentication**
   - User login validation
   - Session management
   - Role verification

2. **Database**
   - Connection testing
   - Table verification
   - Data operations

3. **Game Features**
   - Game scoring
   - Negotiation logic
   - Student playground

4. **External Services**
   - Google Drive operations
   - Email service
   - Metrics collection

### 5.3 Test Credentials

Tests use credentials from `streamlit/.streamlit/secrets.toml`. If the file doesn't exist, tests will run with mock data.

---

## 6. Contributing

### 6.1 Development Workflow

1. Fork the repository:
   - Go to [https://github.com/rbelo/AI-Assistant-Competition](https://github.com/rbelo/AI-Assistant-Competition)
   - Click "Fork" in the top right
   - Clone your fork:
     ```bash
     git clone https://github.com/YOUR_USERNAME/AI-Assistant-Competition.git
     cd AI-Assistant-Competition
     ```

2. Create a new branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. Make your changes and commit:
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

4. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

5. Create a Pull Request:
   - Go to your fork on GitHub
   - Click "New Pull Request"
   - Select your feature branch
   - Fill in the PR description
   - Submit for review

### 6.2 Code Style

- Follow PEP 8 guidelines
- Use type hints
- Write docstrings for all functions
- Keep functions small and focused

### 6.3 Pull Request Process

1. Ensure all tests pass
2. Update documentation if needed
3. Request review from maintainers
4. Address feedback
5. Merge only after approval

---

For more information about specific features or components, refer to the relevant sections in the documentation.
