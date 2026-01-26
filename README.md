# AI Assistant Competition 

A learning platform for students to build AI agents that compete in negotiation challenges. This project is part of the course "AI Impact on Business" at Nova SBE.

---

## Project Overview

### Key Features
- **Multi-agent negotiation**: Host head‑to‑head matches between students' agents
- **Training & evaluation**: Iteratively refine your bot
- **Leaderboard**: Track performance across rounds

### Technical Stack
- **Frontend**: Streamlit for interactive dashboard
- **AI Framework**: Microsoft's AutoGen for agent interactions
- **Database**: PostgreSQL for data persistence
- **Testing**: pytest for comprehensive test coverage

---

## Getting Started

### For Students
1. Read the [User Guide](documentation/USER_GUIDE.md) for:
   - Registration and account setup
   - Interface overview
   - Instructing and submitting agents
   - Negotiation and leaderboard
2. Register and create your account
3. Start building your first agent
4. Test in the playground
5. Submit to competitions

### For Developers

**Quick Start:**
```bash
# Clone and setup
git clone <repository-url>
cd ai-assistant-competition
make venv
make install-dev

# Verify setup
make check

# Run the app
make run
```

**Available Commands:**
| Command | Description |
|---------|-------------|
| `make venv` | Create the virtual environment (Python 3.12 recommended) |
| `make install-dev` | Install all dependencies |
| `make test` | Run all tests |
| `make test-unit` | Run unit tests (fast, no secrets needed) |
| `make test-e2e` | Run E2E tests (requires app running) |
| `make test-cov` | Run tests with coverage report |
| `make lint` | Check code style |
| `make lint-fix` | Auto-fix linting issues |
| `make format` | Format code with Black |
| `make check` | Run lint + tests (CI simulation) |
| `make run` | Start Streamlit app |
| `make run-dev` | Start Streamlit app with auto-login (no auth) |

For detailed documentation, see the [Developer Guide](documentation/DEVELOPER_GUIDE.md).

---

## Project Structure

```
ai-assistant-competition/
├── streamlit/                                   # Main application code
│   ├── 0_Home.py                                # Streamlit entrypoint
│   ├── __init__.py                              # Package initialization
│   ├── modules/                                 # Core functionality modules
│   │   ├── metrics_handler.py                   # Handles analytics and metrics
│   │   ├── database_handler.py                  # Database operations
│   │   ├── negotiations.py                      # Game logic and rules
│   │   ├── student_playground.py                # Testing environment
│   │   ├── email_service.py                     # Email notifications
│   │   ├── game_modes.py                        # Game templates
│   │   ├── schedule.py                          # Competition scheduling
│   │   └── __init__.py                          # Package initialization
│   ├── pages/                                   # Streamlit pages
│   │   ├── 1_Play.py                            # Main game interface
│   │   ├── 2_Control_Panel.py                   # Admin and configuration
│   │   ├── 3_Playground.py                      # Bot testing interface
│   │   └── 4_Profile.py                         # User profile management
│   ├── .streamlit/                              # Streamlit configuration
│   │   └── secrets.toml                         # Environment variables
│   ├── requirements.txt                         # Python dependencies (for Conda)
│   └── environment.yml                          # Conda environment configuration
├── tests/                                       # Test suite
│   ├── unit/                                    # Fast tests (no external deps)
│   ├── integration/                             # Mocked external services
│   ├── e2e/                                     # Playwright end-to-end tests
│   └── unit_tests.py                            # Legacy unit tests
├── documentation/                               # User and developer guides
│   ├── USER_GUIDE.md                            # Student documentation
│   └── DEVELOPER_GUIDE.md                       # Technical documentation
├── E-R_Model/                                   # Database entity-relationship models
│   ├── E-R Model.png                            # Entity-Relationship diagram
│   └── E-R Model.drawio                         # Draw.io source file
├── database/                                    # Database files
│   ├── Tables_AI_Negotiator.sql                 # Database schema
│   ├── Populate_Tables_AI_Negotiator.sql        # Sample data
│   └── students_ai_negotiator.csv               # Student data
├── .devcontainer/                               # Development container configuration
├── .gitignore                                   # Git ignore rules
└── README.md                                    # Project overview
```

---

## Contributing

We welcome contributions! Please see our [Developer Guide](documentation/DEVELOPER_GUIDE.md#9-contribution-workflow) for details on:
- Setting up your development environment
- Code style and standards
- Testing requirements
- Pull request process

---

## References

- Horton, J. J. (2023). Large language models as simulated economic agents: What can we learn from homo silicus? (No. w31122). National Bureau of Economic Research.
- Manning, B. S., Zhu, K., & Horton, J. J. (2024). Automated social science: Language models as scientist and subjects (No. w32381). National Bureau of Economic Research.
- Diliara Zharikova, Daniel Kornev, Fedor Ignatov, Maxim Talimanchuk, Dmitry Evseev, Ksenya Petukhova, Veronika Smilga, Dmitry Karpov, Yana Shishkina, Dmitry Kosenko, and Mikhail Burtsev. 2023. DeepPavlov Dream: Platform for Building Generative AI Assistants. In Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (Volume 3: System Demonstrations), pages 599–607, Toronto, Canada. Association for Computational Linguistics.
- Wu, Q., Bansal, G., Zhang, J., Wu, Y., Zhang, S., Zhu, E., ... & Wang, C. (2023). Autogen: Enabling next-gen llm applications via multi-agent conversation framework.
