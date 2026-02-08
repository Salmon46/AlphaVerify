# AlphaVerify

A comprehensive trading strategy verification and analysis platform.

## Features

## Analysis Tools

Detailed documentation for the statistical analysis modules can be found in [ANALYSIS_TOOLS.md](ANALYSIS_TOOLS.md).

- **Backtesting**: Robust backtesting engine using Backtrader.
- **Walk Forward Analysis (WFA)**: Optimize strategies over rolling windows.
- **Sensitivity Analysis**: Analyze strategy performance across parameter variations.
- **Monte Carlo Simulation (MCS)**: Assess risk and probability of returns.
- **Permutation Tests**: Validate strategy significance against random data.

## Tech Stack

- **Frontend**: React, Vite, TailwindCSS
- **Backend**: Python (FastAPI), Docker
- **Strategy Engine**: Python (Backtrader & Custom Logic)

## Prerequisites

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)

## Setup

1. **Clone the repository**:

   ```bash
   git clone <repository-url>
   cd AlphaVerify
   ```

2. **Configure Environment**:
   Copy `.env.example` to `.env` and fill in your API keys.

   ```bash
   cp .env.example .env
   ```

3. **Start the Application**:

   ```bash
   docker-compose up --build
   ```

4. **Access the Dashboard**:
   Open your browser and navigate to `http://localhost:80`.

## Directory Structure

- `backend/`: FastAPI application and analysis modules.
- `frontend/`: React-based user interface.
- `strategy_engine/`: Core trading strategy logic.
