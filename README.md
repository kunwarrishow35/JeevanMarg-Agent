# JeevanMarg — Self-Healing Emergency Corridor Agent

> AI Multi-Agent System for Emergency Corridor Reliability & Recovery  
> Built for the Kaggle Agents Hackathon with Google ADK

## 🎯 What is JeevanMarg?

Google Maps optimizes routes. **JeevanMarg optimizes corridor reliability.**

JeevanMarg is a production-grade AI multi-agent system that continuously evaluates whether an ambulance can realistically maintain an emergency corridor and automatically recommends recovery actions when corridor reliability drops.

## 🏗️ Architecture

### Tech Stack
| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, TypeScript, Tailwind CSS, Leaflet.js |
| Backend | FastAPI, Python, SQLite |
| AI Agents | Google ADK (5 agents) |
| MCP Servers | FastMCP (4 servers, 10 tools) |
| Deployment | Docker, Google Cloud Run |

### AI Multi-Agent System

```
Emergency Coordinator Agent (Orchestrator)
├── Route Intelligence Agent → Route MCP Server
├── Traffic Intelligence Agent → Traffic MCP Server
├── Trust Score Agent → Trust MCP Server
└── Recovery Agent → Route MCP + Hospital MCP
```

### MCP Servers
- **Traffic MCP**: `get_traffic_status()`, `get_congestion_risk()`, `get_segment_speed()`
- **Route MCP**: `generate_route()`, `estimate_eta()`, `generate_alternative_route()`
- **Hospital MCP**: `get_nearby_hospitals()`, `get_trauma_centers()`
- **Trust MCP**: `calculate_trust_score()`, `assess_reliability()`

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 20+
- Google Gemini API Key ([Get one here](https://aistudio.google.com/))

### 1. Backend Setup
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate    # Windows
# source .venv/bin/activate  # Mac/Linux
pip install -r requirements.txt
```

### 2. Configure API Key
Edit `backend/.env`:
```
GOOGLE_API_KEY=your-gemini-api-key-here
```

### 3. Start Backend
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### 4. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### 5. Open Dashboard
Navigate to [http://localhost:3000](http://localhost:3000)

**Demo Credentials:**
| Role | Username | Password |
|------|----------|----------|
| Dispatcher | dispatcher | dispatch123 |
| Operator | operator | operate123 |
| Admin | admin | admin123 |

## 🎮 Demo Scenarios

Click **"Start Emergency Mission"** to see:

1. **Healthy Corridor** — Trust Score ~94, all clear
2. **Traffic Event** — Trust Score drops to ~58, Recovery Agent activates
3. **Recovery** — Alternative route generated, Trust Score improves 58 → 89

The dashboard shows real-time:
- Agent execution & reasoning
- MCP tool calls with latency
- Trust score gauge with factor breakdown
- Recovery recommendations with approve/reject workflow

## 🐳 Docker Deployment

```bash
# Set your API key
export GOOGLE_API_KEY=your-key-here

# Build and run
docker-compose up --build
```

## 📋 Key Features

- ✅ **Google ADK** — 5 specialized AI agents with reasoning
- ✅ **MCP Servers** — 4 real FastMCP servers with 10 tools
- ✅ **Human-in-the-Loop** — Approval workflow for route changes
- ✅ **Trust Score Engine** — Weighted 5-factor corridor reliability score
- ✅ **Real-time Dashboard** — WebSocket-powered live updates
- ✅ **Role-based Auth** — JWT with dispatcher/operator/admin roles
- ✅ **Map Visualization** — Leaflet.js with route overlays
- ✅ **Docker Deployment** — Production-ready containers

## 📄 License

MIT
