# AlphaVerify Architecture

## Overview

AlphaVerify is a containerized application composed of a Python backend and a React frontend. It leverages Docker for consistent deployment and scalability.

## Components

### Frontend

- **Technology**: React, Vite, TailwindCSS.
- **Role**: Provides the user interface for configuring and visualizing analysis results.
- **Communication**: Communicates with the backend via REST API.

### Backend

- **Technology**: Python (FastAPI).
- **Role**: Handles API requests, data processing, and coordinates analysis tasks.
- **Key Modules**:
  - `routers/`: API endpoints for different analysis types (Backtest, WFA, Sensitivity, MCS, Permutation).
  - `common/`: Shared utilities and data structures.
  - `utils/`: Helper functions.

### Strategy Engine

- **Technology**: Python (Backtrader).
- **Role**: Executes the trading strategy logic during backtesting and analysis.
- **Integration**: The backend invokes the strategy engine to perform simulations.

## Data Flow

1. **User Input**: User configures parameters and uploads data via the Frontend.
2. **API Request**: Frontend sends a request to the Backend.
3. **Processing**: Backend routes the request to the appropriate module.
4. **Execution**: The module may invoke the Strategy Engine or perform statistical analysis.
5. **Response**: Results are processed and returned to the Frontend for visualization.
