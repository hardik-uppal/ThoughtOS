# ContextOS Project Specification
**Date:** November 26, 2025
**Version:** 3.0 (Current State Analysis)

## 1. Executive Summary
The project is currently in a **transitional state** between a prototype and a production-ready application.
-   **Legacy/Prototype**: A functional **Streamlit** application (`app.py`) that interacts directly with the backend logic.
-   **Target Architecture**: A decoupled **React** frontend (`frontend/`) communicating with a **FastAPI** backend (`backend/main.py`).

Both interfaces share the same core business logic and data layer, ensuring data consistency. The current focus appears to be on building out the React frontend and the Onboarding experience.

## 2. System Architecture

```mermaid
graph TD
    subgraph "Frontend Layer"
        React[React App (frontend/)] -->|REST API| API[FastAPI Server (backend/main.py)]
        Streamlit[Streamlit App (app.py)] -.->|Direct Import| Logic
    end

    subgraph "Backend Layer"
        API -->|Import| Logic[Core Logic (logic/)]
        Logic --> Agent[Agent Orchestrator]
        Logic --> Ingestion[Ingestion Engine]
        Logic --> SQL[SQL Engine]
        Logic --> Graph[Graph Manager]
    end

    subgraph "Data Layer"
        SQL --> SQLite[(SQLite DB)]
        Graph --> Neo4j[(Neo4j Graph)]
    end

    subgraph "External Integrations"
        Ingestion --> Plaid[Plaid API]
        Ingestion --> GCal[Google Calendar]
    end
```

## 3. Module Breakdown

### 3.1 Frontend Layer
#### **A. React Application (`frontend/`)**
-   **Tech Stack**: React, TypeScript, Vite.
-   **Status**: Active Development.
-   **Key Components**:
    -   `App.tsx`: Main entry, handles chat state and routing.
    -   `components/Onboarding/`: Dedicated wizard for user setup (Financial & Productivity calibration).
    -   `components/WidgetRenderer.tsx`: Renders dynamic widgets (forms, cards) from Agent responses.
    -   `components/Sidebar`: Context switching and navigation.

#### **B. Streamlit Application (`app.py`)**
-   **Tech Stack**: Streamlit (Python).
-   **Status**: Functional Prototype / Admin Tool.
-   **Key Features**:
    -   Direct database manipulation.
    -   "Curator" tab for human-in-the-loop data enrichment.
    -   "Admin" tab for system logs and causal analysis.
    -   Manual Plaid/Google Auth debugging.

### 3.2 Backend API (`backend/main.py`)
-   **Tech Stack**: FastAPI.
-   **Role**: Serves the React frontend.
-   **Key Endpoints**:
    -   `POST /api/chat`: Main agent interface.
    -   `POST /api/sync`: Triggers Plaid/Calendar sync.
    -   `GET /api/context`: Fetches "Context Rail" data (Energy, Events, Tasks).
    -   `GET /api/onboarding/*`: Manages onboarding state and rules.
    -   `GET /api/auth/*`: Handles Plaid link token generation and exchange.

### 3.3 Core Logic (`logic/`)
This is the shared "Brain" of the application.
-   **`agent.py`**: The central orchestrator. Routes user input to:
    1.  **Template Engine**: For logging structured data (forms).
    2.  **Reasoning Engine**: For RAG-based queries.
    3.  **Command Handlers**: For specific actions like "backfill".
-   **`sql_engine.py`**: Abstraction over SQLite. Handles CRUD for Events, Transactions, Thoughts, and Logs.
-   **`graph_db.py`**: Abstraction over Neo4j. Manages nodes (Event, Transaction, Merchant, Person) and relationships.
-   **`ingestion.py`**: Orchestrates data fetching from Integrations and syncing to DBs.
-   **`enrichment_agent.py`**: AI agent for categorizing transactions and linking entities (used in Curator mode).
-   **`onboarding_agent.py`**: Logic for the new onboarding flow (financial rules, productivity settings).

### 3.4 Data Layer
-   **SQLite (`context_os.db`)**: Source of Truth for raw data.
-   **Neo4j**: Derived Knowledge Graph for complex queries and insights (e.g., "Spending by Category", "Top Merchants").

## 4. Key Workflows

### 4.1 Data Ingestion & Sync
1.  **Trigger**: User clicks "Sync" or API call to `/api/sync`.
2.  **Process**:
    -   `fetch_transactions` (Plaid) -> `upsert_transaction` (SQLite).
    -   `fetch_events` (Google) -> `upsert_event` (SQLite).
    -   `sync_to_graph`: Pushes new SQLite rows to Neo4j nodes.
    -   `run_enrichment`: Links nodes (e.g., Transaction -> Merchant) in Neo4j.

### 4.2 Chat & Reasoning
1.  **Input**: User sends message via React Chat or Streamlit.
2.  **Agent Routing**:
    -   If "log/record" -> Returns a **Form Widget** (JSON).
    -   If "backfill" -> Triggers background job.
    -   Else -> Calls `ReasoningEngine`.
3.  **Reasoning**:
    -   Retrieves context from Graph/SQL.
    -   Generates natural language response.
    -   Returns response + optional UI widgets.

### 4.3 Onboarding (New)
1.  **Flow**: Welcome -> Financial Calibration -> Productivity Calibration -> Complete.
2.  **Logic**:
    -   `OnboardingAgent` generates questions based on user data.
    -   User answers are saved as **Rules** (e.g., "Uber is always Transport").
    -   Completing onboarding sets a flag and triggers initial defaults.

## 5. Gaps & Observations

### 5.1 Architecture Gaps
-   **Auth Security**: The FastAPI endpoints (`/api/*`) currently have **no authentication**. Anyone with network access can query data.
-   **Streamlit Dependency**: The Streamlit app is still the only place for certain Admin tasks (Clearing logs, Manual Causal Analysis, "Curator" review queue). These need to be ported to the React Admin Panel.

### 5.2 Functional Gaps
-   **Onboarding Integration**: The `OnboardingAgent` exists but it's unclear if the React frontend fully utilizes all its capabilities (e.g., `calibrate_finance_endpoint` returns questions, but are they rendered?).
-   **Real-time Updates**: No WebSocket support. Chat is request-response. Long-running tasks (Backfill) rely on polling or user patience.

### 5.3 Code Quality
-   **Testing**: No visible unit or integration tests in the file structure.
-   **Error Handling**: Basic try/except blocks in API. Needs a global exception handler.

## 6. Recommendations
1.  **Port Admin Features**: Move the "Curator" (Human-in-the-loop) and "Log Viewer" features from Streamlit to the React Admin Panel to fully deprecate Streamlit.
2.  **Secure API**: Implement JWT or Session-based auth for the FastAPI backend.
3.  **Consolidate Frontend**: Decide on a cut-over date to make React the primary interface.
