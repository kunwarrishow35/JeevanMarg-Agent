# 🚑 JeevanMarg — Self-Healing Emergency Corridor AI Agent System

> **AI Multi-Agent Emergency Corridor Reliability & Recovery Platform**
>
> Built using **Google ADK**, **FastMCP**, **FastAPI**, **Next.js**, and **OSRM**
>
> Developed for the **Kaggle 5-Day AI Agents Intensive Vibe Coding Capstone**

---

# 🚨 Problem Statement

Every second matters during medical emergencies.

Traditional navigation systems optimize for the **fastest route**, but they do not continuously evaluate whether an emergency corridor remains reliable after unexpected events such as:

- Major road accidents
- Sudden congestion
- Road blocks
- Signal failures
- Weather disruptions

As a result, ambulances may still encounter blocked or unreliable corridors even after selecting the "best" route.

JeevanMarg addresses this problem using an **AI Multi-Agent Architecture** that continuously monitors corridor reliability, calculates a dynamic Trust Score, and recommends recovery actions before delays become critical.

---

# 💡 Solution

Unlike traditional navigation systems,

> **Google Maps optimizes routes.**
>
> **JeevanMarg optimizes corridor reliability.**

JeevanMarg continuously monitors an emergency corridor using multiple specialized AI agents.

When corridor reliability decreases below an acceptable threshold, the system automatically:

- detects degradation
- calculates Trust Score
- generates an alternative route
- requests operator approval
- stabilizes the emergency corridor

---

# 🤖 Why AI Agents?

Emergency corridor management requires multiple independent reasoning tasks.

Instead of relying on a single AI model, JeevanMarg decomposes the workflow into specialized agents.

Each agent focuses on one responsibility while collaborating through Google ADK orchestration.

This makes the system:

- Modular
- Explainable
- Scalable
- Easier to extend

---

# 🏗️ System Architecture

## AI Multi-Agent Workflow

```
Emergency Coordinator Agent
        │
        ▼
 ┌─────────────────────┐
 │ Route Intelligence  │
 └─────────────────────┘
        │
        ▼
 ┌─────────────────────┐
 │ Traffic Intelligence│
 └─────────────────────┘
        │
        ▼
 ┌─────────────────────┐
 │ Trust Score Agent   │
 └─────────────────────┘
        │
        ▼
 Trust Below Threshold?
        │
      YES
        │
        ▼
 ┌─────────────────────┐
 │ Recovery Agent      │
 └─────────────────────┘
        │
        ▼
 Human Approval
        │
        ▼
 Corridor Stabilized
```

---

## Architecture Diagram

![JeevanMarg System Architecture Diagram](docs/images/architecture.png)

Detailed architecture details can be found in the [architecture.md](file:///c:/Users/kunwa/Desktop/JeevanMarg-Agent/docs/architecture.md) documentation.


---

# 🛠 Technology Stack

| Layer | Technology |
|---------|------------|
| Frontend | Next.js 15, TypeScript, Tailwind CSS |
| Backend | FastAPI |
| Database | SQLite |
| Maps | Leaflet.js + OSRM |
| AI Agents | Google ADK |
| MCP | FastMCP |
| Authentication | JWT |
| Realtime | WebSockets |
| Deployment | Docker |

---

# 🧠 AI Agents

## Emergency Coordinator

Coordinates all specialist agents and orchestrates the emergency workflow.

---

## Route Intelligence Agent

Responsibilities

- Generate primary route
- Generate recovery route
- Estimate ETA

Uses:

- Route MCP

---

## Traffic Intelligence Agent

Responsibilities

- Analyze congestion
- Evaluate bottlenecks
- Detect degraded corridor

Uses:

- Traffic MCP

---

## Trust Score Agent

Responsibilities

Calculates corridor reliability using:

- Congestion
- Route Stability
- ETA Confidence
- Corridor Continuity
- Traffic Volatility

---

## Recovery Agent

Responsibilities

- Generate alternative route
- Estimate improvements
- Request operator approval

---

# 🔧 MCP Servers

## Route MCP

- generate_route()
- estimate_eta()
- generate_alternative_route()

---

## Traffic MCP

- get_traffic_status()
- get_congestion_risk()
- get_segment_speed()

---

## Trust MCP

- calculate_trust_score()
- assess_reliability()

---

## Hospital MCP

- get_nearby_hospitals()
- get_trauma_centers()

---

# 🚀 Features

- ✅ Google ADK Multi-Agent Architecture
- ✅ FastMCP Tool Servers
- ✅ Human-in-the-loop Decision Making
- ✅ Dynamic Trust Score Engine
- ✅ Incident Simulation
- ✅ Alternative Route Generation
- ✅ Real Road Routing using OSRM
- ✅ WebSocket Realtime Updates
- ✅ Role Based Dashboard
- ✅ Dispatcher / Operator / Admin
- ✅ JWT Authentication
- ✅ Fullscreen Interactive Map
- ✅ Recovery Recommendation Engine
- ✅ Mission Timeline
- ✅ Docker Ready

---

# 📷 Screenshots

## Dashboard

> Add Image

```
docs/images/dashboard.png
```

---

## Healthy Corridor

> Add Image

```
docs/images/healthy_corridor.png
```

---

## Major Accident Simulation

> Add Image

```
docs/images/incident.png
```

---

## Recovery Recommendation

> Add Image

```
docs/images/recovery.png
```

---

## Mission Stabilized

> Add Image

```
docs/images/mission_stabilized.png
```

---

# 🔄 Demo Workflow

1. Dispatcher creates emergency mission.

2. Coordinator launches AI agents.

3. Route Agent generates emergency corridor.

4. Traffic Agent evaluates corridor health.

5. Trust Agent computes corridor reliability.

6. Major accident is simulated.

7. Trust Score decreases.

8. Recovery Agent generates safer route.

9. Operator reviews recommendation.

10. Alternative route approved.

11. Corridor stabilizes.

12. Trust Score improves.

---

# 📊 Real vs Simulated Components

| Component | Status |
|-----------|--------|
| Google ADK Agents | ✅ Real |
| FastMCP Servers | ✅ Real |
| FastAPI Backend | ✅ Real |
| WebSockets | ✅ Real |
| JWT Authentication | ✅ Real |
| OSRM Road Routing | ✅ Real |
| Incident Simulation | 🔶 Simulated |
| Trust Score Engine | 🔶 Rule-based |
| Emergency Dispatch Network | 🔶 Simulated |

---

# 🚀 Quick Start

## Prerequisites

- Python 3.10+
- Node.js 20+
- Google Gemini API Key

---

## Backend

```bash
cd backend

python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt

uvicorn app.main:app --reload --port 8000
```

---

## Frontend

```bash
cd frontend

npm install

npm run dev
```

---

## Environment Variables

Copy

```
backend/.env.example
```

to

```
backend/.env
```

Then replace

```
GOOGLE_API_KEY
```

with your own Gemini API key.

---

# 🔑 Demo Credentials

| Role | Username | Password |
|------|----------|----------|
| Dispatcher | dispatcher | dispatch123 |
| Operator | operator | operate123 |
| Admin | admin | admin123 |

---

# 🌍 Future Work

- Live Google Maps Traffic Integration
- Ambulance GPS Tracking
- Government Traffic Signal Integration
- Hospital Capacity Prediction
- Predictive Congestion Forecasting
- Mobile Application
- Cloud Deployment
- Multi-city Support

---

# 🙏 Acknowledgements

- Google AI Developer Platform
- Google ADK
- FastMCP
- OSRM
- FastAPI
- Next.js
- Kaggle 5-Day AI Agents Intensive Vibe Coding Course

---

# 📄 License

MIT License