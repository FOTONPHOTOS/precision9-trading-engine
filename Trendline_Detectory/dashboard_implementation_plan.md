# Mission Control Dashboard: Implementation Plan

This document outlines the phased implementation plan for building a comprehensive, real-time dashboard and control center for the Arsenal trading bot ecosystem.

## Architecture Overview

The system will be built around a central **WebSocket Pub/Sub Hub**.

1.  **Central Hub (`dashboard_server.py`):** A Python FastAPI server that acts as a real-time message broker. All backend components connect to it.
2.  **Data Emitters (`dashboard_client.py`):** A simple client module that Arsenal, Aegis, and Helios will use to send their data (health, logs, analysis, state) to the Hub.
3.  **Frontend (`dashboard_frontend/`):** A modern React single-page application that connects to the Hub, subscribes to the data streams, and visualizes everything in a user-friendly interface.
4.  **Persistent Storage:** The **Aegis SQLite database** will serve as the system's persistent memory. The Hub will have read-access to serve historical data, and the frontend will load this on startup.

This architecture ensures real-time updates, avoids the previous Redis memory issues, and allows for bidirectional communication (e.g., for a "Start System" button).

---

## Phased Implementation

### Phase 1: Backend "Nervous System"

**Objective:** Create the core infrastructure for real-time data transmission.

1.  **Create the WebSocket Hub (`dashboard_server.py`):**
    *   Use FastAPI to create a server.
    *   Implement a primary WebSocket endpoint (`/ws`) to manage connections.
    *   Implement logic to differentiate between 'bot' emitters and 'dashboard' listeners.
    *   Create a broadcast function to relay all messages from bots to all connected dashboards.
    *   Create an HTTP endpoint (`/api/history/trades`) to read and serve all trades from the Aegis SQLite DB.

2.  **Create the Emitter Module (`dashboard_client.py`):**
    *   Develop a Python class (`Emitter`) that handles connecting to the WebSocket Hub.
    *   Implement automatic reconnection logic to ensure a persistent link.
    *   Provide simple methods (`emit_health`, `emit_data`, `emit_log`) for other applications to use.

3.  **Integrate Emitter into All Components:**
    *   **Aegis (`trade_manager.py`):** Modify to initialize and use the `Emitter`. It will send heartbeats, risk state changes (cooldowns), new/closed trade events, and Bybit account balance updates.
    *   **Arsenal (`live_arsenal_horus_integrated.py`):** Modify to initialize the `Emitter` (one for each symbol). It will send its full `MarketIntelligence` and `IntelligentDecision` objects after each analysis cycle. It will also report API rate limit warnings.
    *   **Helios (`helios_server.py`):** Modify to initialize the `Emitter`. It will send the master `helios_context` (BTC trend, sentiment) after each update.

### Phase 2: Frontend "Mission Control" UI

**Objective:** Build a professional, data-rich, and intuitive user interface.

1.  **Scaffold React Project:**
    *   Create a `dashboard_frontend` directory.
    *   Use `npm create vite@latest` to initialize a new React + TypeScript project.
    *   Install core dependencies: `mui-material` (for UI components), `zustand` (for state management), and `recharts` (for visualizations).

2.  **Establish Core Frontend Services:**
    *   Implement a central WebSocket client service to connect to the Hub.
    *   Set up a Zustand state management store to act as the single source of truth for all data received from the backend.

3.  **Develop UI Components:**
    *   **Main Layout:** A persistent sidebar for navigation and a header for system-wide status/controls.
    *   **Overview Page:** A high-level dashboard showing the health of all components, a system-wide event log, and key performance indicators (Total PnL, Win Rate).
    *   **Aegis Page:** Cards to visualize cooldown timers and risk states. A detailed, sortable table of all historical and active trades.
    *   **Arsenal Page:** A grid layout of "Symbol Cards". Each card will represent a running Arsenal instance (e.g., SOLUSDT) and visualize its latest `MarketIntelligence` data using gauges, indicators, and text.
    *   **Helios Page:** A simple card displaying the current master market context.

### Phase 3: Remote Control Functionality

**Objective:** Add the ability to start the trading system from the dashboard.

1.  **Add Control Endpoint to Hub:** Create an HTTP endpoint (`/api/control/start`) on the `dashboard_server.py`.
2.  **Implement `subprocess` Logic:** This endpoint will use Python's `subprocess.Popen` to execute the `launch_all_bots.ps1` script in a detached process.
3.  **Add UI Button:** Place a "Start System" button in the dashboard's header that makes a POST request to the new control endpoint.
