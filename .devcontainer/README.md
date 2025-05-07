# Developer Manual

This document guides you through the process of setting up, running, and contributing to the **AI-Assistant-Competition** platform using our DevContainer. By encapsulating dependencies, tooling, and environment configuration in a container, we ensure that every developer—regardless of host OS—has a reproducible, fully-featured workspace.

---

## 1. Prerequisites & Rationale

Before launching the container, you need:

- **Docker Engine** (version 20.10+): provides the underlying container runtime.  
- **VS Code** with **Remote - Containers** extension: lets you open and work inside containers as if they were local folders.  
- **Git CLI**: for branch management, commits, and interacting with remote repositories.

> **Why containers?**  
> Containers eliminate the “it works on my machine” problem by bundling specific Python, Node.js, database clients, and CLI tools into a single image. This ensures consistency across all contributors.

---

## 2. DevContainer Configuration

All DevContainer settings live in `.devcontainer/devcontainer.json`:

- **Base Image**  
  We derive from Microsoft’s official Python 3.10 image, augmented with Docker-in-Docker and Node.js.  
- **Features & Extensions**  
  We install the PostgreSQL client and auto-formatters (e.g. `black`, `flake8`) so code style checks run out of the box.  
- **Post-Create Hook**  
  After container creation, a script (`.devcontainer/setup.sh`) bootstraps environment variables and optionally initializes the database.

If you need to tweak memory limits, add VS Code extensions, or include extra CLI tools, update `devcontainer.json` here and commit your changes.

---

## 3. Launching Your DevContainer

1. **Clone the repository (if you haven’t already)**  
   ```bash
   git clone https://github.com/your-org/AI-Assistant-Competition.git
   cd AI-Assistant-Competition
