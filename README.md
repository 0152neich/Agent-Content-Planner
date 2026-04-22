# Agent-Content-Planner
A full-stack application for AI-assisted content planning and publishing workflows.

## Overview
This project implements a full-stack system featuring:

- A FastAPI backend with modular domain-driven structure
- A React + TypeScript frontend powered by Vite
- TanStack Router for route management with lazy-loaded pages
- MUI theming with light and dark mode support
- i18n support for internationalized UI content
- PostgreSQL persistence and Docker-based local orchestration

## Components

### Backend
- **FastAPI Application**: REST API with versioned routes under `/api/v1`
- **Authentication Layer**: JWT-based auth and social OAuth integrations
- **Content Planning Services**: Project, conversation, and history management
- **Database Layer**: PostgreSQL + SQLAlchemy integrations
- **Infrastructure Utilities**: Logging, error handling, and shared runtime helpers

### Frontend
- **React Application**: Feature-based frontend architecture
- **Routing**: TanStack Router with generated route tree
- **Theme System**: MUI-based design tokens and color mode context
- **Internationalization**: i18next setup with language switching support
- **API Client**: Axios-based request handling with auth/error handling

## Getting Started

### Prerequisites
- Docker and Docker Compose (recommended for full stack)
- Python 3.11+
- Node.js 20+
- npm 10+

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/0152neich/Agent-Content-Planner.git
   cd Agent-Content-Planner
   ```

2. Create environment files:
   ```bash
   # backend
   cp .env.example .env

   # frontend
   cp frontend/.env.example frontend/.env
   ```
   On Windows PowerShell, use:
   ```powershell
   Copy-Item .env.example .env
   Copy-Item frontend/.env.example frontend/.env
   ```

3. Start with Docker Compose:
   ```bash
   make dev
   ```
   Or:
   ```bash
   docker compose -f docker-compose.dev.yml up --build
   ```

## Project Structure
```text
Agent-Content-Planner/
|-- src/                              # Backend FastAPI application
|   |-- api/                          # API routes and request handling
|   |-- app/                          # Application services/use cases
|   |-- domain/                       # Core business entities and rules
|   |-- infra/                        # Infrastructure and integrations
|   |-- shared/                       # Shared helpers, logging, utilities
|   |-- tests/                        # Backend tests
|   `-- main.py                       # FastAPI entrypoint
|-- frontend/                         # Frontend React application
|   |-- src/
|   |   |-- components/               # Shared UI components
|   |   |-- features/                 # Feature modules
|   |   |-- i18n/                     # i18n configuration and translations
|   |   |-- routes/                   # TanStack Router route definitions
|   |   `-- theme/                    # MUI theme and color mode setup
|   |-- package.json                  # Frontend dependencies and scripts
|   `-- vite.config.ts                # Vite configuration
|-- docker-compose.dev.yml            # Development stack (backend/frontend/postgres)
|-- docker-compose.prod.yml           # Production compose file
|-- requirements.txt                  # Backend dependencies
|-- Makefile                          # Dev/prod convenience commands
`-- README.md
```

## Usage
Once the application is running:

1. Open frontend at `http://localhost:5173`
2. Backend API is available at `http://localhost:8000`
3. API docs are available at `http://localhost:8000/docs`

For local non-Docker run:
```bash
# backend
pip install -r requirements.txt
python src/main.py

# frontend (new terminal)
cd frontend
npm install
npm run dev
```

## Dependencies

### Backend
- fastapi
- uvicorn
- sqlalchemy
- psycopg
- pydantic
- crewai
- langchain-openai
- langchain-anthropic
- langchain-google-genai

### Frontend
- react
- typescript
- vite
- axios
- @tanstack/react-router
- @tanstack/react-query
- @mui/material
- i18next
- react-i18next
