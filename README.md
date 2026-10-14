# 🔎 Deep Research AI

> **A fully deployed, autonomous AI research platform that transforms any natural-language question into a comprehensive, citation-backed research report.**

🌐 **Live Demo:** [https://deep-research-ai-wine.vercel.app](https://deep-research-ai-wine.vercel.app)
🔧 **Backend API:** [https://deep-research-ai-38l8.onrender.com](https://deep-research-ai-38l8.onrender.com)

---

## ✨ What It Does

Instead of a single LLM response, Deep Research AI runs a **full autonomous research pipeline**:

```
User Query
   ↓
Research Planner  (Gemini AI)
   ↓
Multi-Source Web Search  (Tavily · Serper · DuckDuckGo · Google News · Wikipedia · OpenAlex · Crossref)
   ↓
Source Collection & Content Extraction
   ↓
Evidence Engine & Claim Analysis
   ↓
Independent Claim Verification
   ↓
Gemini Analysis & Synthesis
   ↓
Structured Report with Citations
```

---

## 🚀 Features

| Feature | Description |
|---|---|
| 🧠 **Autonomous Planning** | Converts a high-level question into a step-by-step research plan |
| 🌐 **Multi-Source Search** | Searches Tavily, Serper, DuckDuckGo, Google News, Wikipedia, OpenAlex, Crossref |
| 📚 **Academic Research** | Integrates peer-reviewed papers via OpenAlex and Crossref |
| 🔬 **Evidence Engine** | Stores claims with supporting/contradicting source links and confidence scores |
| ✅ **Claim Verification** | Cross-checks key claims against independent sources (excludes original domains) |
| ⚡ **Parallel Execution** | Independent research tasks run concurrently via an in-memory queue |
| 📊 **Structured Reports** | Executive summary, findings, competitive landscape, risks, citations |
| 🤖 **Gemini AI** | Powered by Google Gemini for planning, analysis, and synthesis |
| 🔐 **Auth System** | JWT-based login/register with access + refresh tokens |
| 📱 **Glassmorphism UI** | 3D animated React frontend with real-time job tracking |
| 📈 **Research History** | Full history of all past research jobs, persistent across sessions |
| 🔄 **Live Status Polling** | Real-time pipeline stage tracking (planning → searching → analyzing → done) |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    VERCEL (Frontend)                        │
│  React + Vite · react-router-dom · @react-three/fiber       │
│  Dashboard · Reports · Agents · Settings · Login/Register   │
└───────────────────────┬─────────────────────────────────────┘
                        │  HTTPS (REST API)
┌───────────────────────▼─────────────────────────────────────┐
│                   RENDER (Backend)                          │
│  Node.js · Express · JWT Auth · CORS · In-Memory Queue      │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Auth Routes  │  │Research Routes│  │  Report Routes   │  │
│  └──────────────┘  └──────┬───────┘  └──────────────────┘  │
│                           │                                 │
│  ┌────────────────────────▼────────────────────────────┐   │
│  │              Research Pipeline                      │   │
│  │  queryPlanner → researchEngine → evidenceEngine    │   │
│  │  sourceCollector → verificationEngine              │   │
│  │  geminiService → reportGenerator                   │   │
│  └────────────────────────────────────────────────────┘   │
└───────────────────────┬─────────────────────────────────────┘
                        │
          ┌─────────────┴──────────────┐
          │                            │
┌─────────▼──────────┐     ┌──────────▼──────────┐
│  MongoDB Atlas     │     │  Google Gemini API   │
│  Users · Research  │     │  Planning · Analysis │
│  Reports · History │     │  Synthesis · Answers │
└────────────────────┘     └─────────────────────┘
```

---

## 🛠️ Technology Stack

### Frontend
| Technology | Purpose |
|---|---|
| **React 19** | UI framework |
| **Vite 8** | Build tool & dev server |
| **react-router-dom v7** | Client-side routing |
| **@react-three/fiber** | 3D animated background |
| **@react-three/drei** | Three.js helpers (Stars, Float, Distort) |
| **three.js** | 3D rendering engine |
| **lucide-react** | Icon library |
| **react-markdown + remark-gfm** | Report rendering with GitHub Markdown |
| **axios** | HTTP client with JWT interceptors & auto-refresh |
| **Vanilla CSS** | Custom glassmorphism design system |

### Backend
| Technology | Purpose |
|---|---|
| **Node.js + Express** | REST API server |
| **MongoDB Atlas + Mongoose** | Persistent data storage |
| **JWT (access + refresh)** | Stateless authentication |
| **cors** | Cross-origin request handling |
| **@google/genai (Gemini)** | AI planning, analysis & synthesis |
| **Tavily API** | Premium web search |
| **Serper API** | Google search results |
| **DuckDuckGo HTML** | Free fallback search |
| **Google News RSS** | News source discovery |
| **Wikipedia API** | Encyclopedic reference |
| **OpenAlex API** | Academic paper search |
| **Crossref API** | Academic citation lookup |
| **In-memory job queue** | Background research execution |
| **bcryptjs** | Password hashing |
| **nodemailer** | Email (SMTP) |

### Infrastructure & Deployment
| Service | Role |
|---|---|
| **Vercel** | Frontend hosting (CDN + SPA routing) |
| **Render** | Backend hosting |
| **MongoDB Atlas** | Cloud database |
| **GitHub** | Source control + CI/CD trigger |

---

## 📁 Project Structure

```
deep_research_ai/
├── frontend/                        # React + Vite SPA
│   ├── src/
│   │   ├── api/
│   │   │   ├── axios.js             # Axios instance (JWT interceptors, auto-refresh)
│   │   │   ├── auth.js              # Auth API calls (login, register, me)
│   │   │   ├── research.js          # Research API calls
│   │   │   ├── session.js           # Token storage & session management
│   │   │   └── errorMessage.js      # Error normalizer
│   │   ├── components/
│   │   │   └── 3d/Scene3D.jsx       # Three.js animated background
│   │   ├── context/
│   │   │   ├── AuthContext.jsx      # Auth state (user, login, logout, restore)
│   │   │   ├── ResearchContext.jsx  # Research history & job tracking
│   │   │   └── ThemeContext.jsx     # Light/dark theme
│   │   ├── pages/
│   │   │   ├── DashboardPage.jsx    # Main research interface
│   │   │   ├── ReportsPage.jsx      # Past reports viewer
│   │   │   ├── AgentsPage.jsx       # Pipeline stage visualizer
│   │   │   ├── SettingsPage.jsx     # User settings
│   │   │   ├── LoginPage.jsx        # Login form
│   │   │   └── RegisterPage.jsx     # Registration form
│   │   ├── App.jsx                  # Router + error boundary
│   │   ├── main.jsx                 # React entry point
│   │   └── index.css                # Global design system (glassmorphism)
│   ├── vercel.json                  # Vercel SPA rewrite rules
│   ├── vite.config.js               # Vite config + dev proxy to backend
│   └── package.json
│
├── backend/                         # Node.js + Express API
│   ├── src/
│   │   ├── server.js                # Express app (CORS, routes, error handler)
│   │   ├── config/db.js             # MongoDB connection
│   │   ├── routes/
│   │   │   ├── authRoutes.js        # /auth/*
│   │   │   ├── researchRoutes.js    # /research/*
│   │   │   ├── reportRoutes.js      # /reports/*
│   │   │   ├── adminRoutes.js       # /admin/*
│   │   │   └── aiRoutes.js          # /ai/* (Gemini quick-answer)
│   │   ├── controllers/             # Route handler logic
│   │   ├── models/                  # Mongoose schemas (User, Research, Report)
│   │   ├── middleware/
│   │   │   └── databaseReady.js     # Blocks requests until DB is connected
│   │   ├── services/
│   │   │   ├── geminiService.js     # Gemini AI integration (planning, synthesis)
│   │   │   ├── researchEngine.js    # Core research orchestration
│   │   │   ├── queryPlanner.js      # Converts query → research tasks
│   │   │   ├── sourceCollector.js   # Multi-provider web search
│   │   │   ├── contentExtractor.js  # Web page content extraction
│   │   │   ├── evidenceEngine.js    # Claim & evidence management
│   │   │   ├── verificationEngine.js# Independent claim verification
│   │   │   ├── reportGenerator.js   # Final report assembly
│   │   │   ├── researchStateMachine.js # Job state transitions
│   │   │   ├── researchQueue.js     # In-memory job queue
│   │   │   └── researchHttp.js      # HTTP helpers for research
│   │   ├── queue/                   # Job queue management
│   │   ├── workers/                 # Background worker process
│   │   └── utils/                   # Shared utilities
│   ├── Dockerfile
│   └── package.json
│
├── deploy/
│   └── grafana/dashboards/          # Observability dashboards
├── docker-compose.prod.yml          # Production Docker Compose
├── run.ps1                          # Windows dev launcher
└── README.md
```

---

## 🔌 API Reference

### Authentication

```http
POST /api/v1/auth/register       # Register new user
POST /api/v1/auth/login          # Login → returns access + refresh tokens
POST /api/v1/auth/refresh        # Refresh access token
POST /api/v1/auth/logout         # Logout
GET  /api/v1/auth/me             # Get current user profile
```

### Research

```http
POST   /api/v1/research          # Start a new research job
GET    /api/v1/research          # List all research jobs for user
GET    /api/v1/research/:id      # Get research job details + status
DELETE /api/v1/research/:id      # Delete a research job
```

### Reports

```http
GET /api/v1/reports              # List all generated reports
GET /api/v1/reports/:id          # Get a specific report
```

### AI Quick Answer

```http
POST /api/v1/ai/answer           # Gemini-powered quick answer
POST /api/v1/quick-answer        # Alias
```

### Health

```http
GET /health                      # Server + DB + provider status
```

---

## 🔄 Research Pipeline Stages

Each research job progresses through these tracked stages:

```
pending → planning → searching → collecting → extracting
        → analyzing → verifying → synthesizing → completed
                                               ↘ failed
```

The frontend polls the job status and updates the UI in real-time as each stage completes.

---

## 🖥️ Frontend Pages

| Page | Route | Description |
|---|---|---|
| **Dashboard** | `/dashboard` | Submit queries, track active research, view results |
| **Reports** | `/reports` | Browse and read all past research reports |
| **Agents** | `/agents` | Visualize the research pipeline and agent statuses |
| **Settings** | `/settings` | User profile and account preferences |
| **Login** | `/login` | JWT authentication |
| **Register** | `/register` | New account creation |

---

## 🔐 Authentication Flow

```
Register/Login
     ↓
Backend returns { accessToken, refreshToken }
     ↓
Frontend stores in localStorage
     ↓
axios interceptor attaches Bearer token to every request
     ↓
On 401 → auto-refresh via refreshToken → retry original request
     ↓
On refresh failure → logout + redirect to /login
```

---

## 🌐 Deployment

### Frontend — Vercel

The frontend is deployed on **Vercel** with SPA routing handled by `vercel.json`:

```json
{
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
}
```

The axios client automatically routes to the Render backend in production builds via a hardcoded fallback (no Vercel env vars required).

### Backend — Render

The Express backend runs on **Render**. CORS is configured via the `CORS_ORIGINS` environment variable to allow the Vercel frontend origin.

**Required environment variables on Render:**

| Variable | Value |
|---|---|
| `CORS_ORIGINS` | `http://localhost:5173,https://deep-research-ai-wine.vercel.app` |
| `MONGODB_URL` | Your MongoDB Atlas connection string |
| `JWT_ACCESS_SECRET` | Strong random secret |
| `JWT_REFRESH_SECRET` | Strong random secret |
| `GEMINI_API_KEY` | Google AI Studio API key |
| `TAVILY_API_KEY` | Tavily search API key (optional) |
| `SERPER_API_KEY` | Serper.dev API key (optional) |

---

## 💻 Local Development

### Prerequisites
- Node.js 18+
- MongoDB (local or Atlas)

### 1. Clone the repo

```bash
git clone https://github.com/joshipriyanshu125/deep_research_ai.git
cd deep_research_ai
```

### 2. Backend setup

```bash
cd backend
npm install
# Copy and fill in your environment variables
cp .env.example .env
node src/server.js
```

Backend runs at `http://localhost:5000`

### 3. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`

The Vite dev server proxies all `/api/*` requests to `http://localhost:5000` automatically — no extra config needed.

### One-command startup (Windows)

```powershell
.\run.ps1
```

---

## 🧪 Testing

```bash
# Frontend tests
cd frontend && npm test

# Backend tests
cd backend && npm test
```

---

## 📈 Observability

The backend exposes a `/health` endpoint with full system status:

```json
{
  "status": "ok",
  "database": "connected",
  "gemini": { "configured": true, "model": "gemini-flash-lite-latest" },
  "searchProviders": {
    "tavily": true,
    "serper": true,
    "duckduckgo": true,
    "googleNews": true,
    "wikipedia": true,
    "openalex": true,
    "crossref": true
  }
}
```

Grafana dashboards are available in `deploy/grafana/dashboards/`.

---

## 🤝 Contributing

```bash
git clone https://github.com/joshipriyanshu125/deep_research_ai.git
git checkout -b feature/your-feature
# make changes
git commit -m "feat: your feature"
git push origin feature/your-feature
```

Then open a Pull Request.

---

## 📜 License

MIT License — see [LICENSE](./LICENSE)

---

## 👨‍💻 Author

**Priyanshu Joshi** · [joshipriyanshu125@gmail.com](mailto:joshipriyanshu125@gmail.com)

---

> **Build an AI research assistant that doesn't just answer — it investigates, verifies, reasons, and reports.**
