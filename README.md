# 🛡️ PhishGuard AI

> **Real-Time AI-Powered Email Phishing Detection System**
> Detects phishing emails as they arrive — explains *why* each email is dangerous, with live WebSocket updates and an explainable risk score.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.1xx-009688?style=flat-square&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)
![scikit-learn](https://img.shields.io/badge/scikit--learn-TF--IDF%20%2B%20LogReg-F7931E?style=flat-square&logo=scikitlearn&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)

**Author:** [Vaibhavi Nirgude](https://github.com/virendrabamne010) · virendrabamne010@gmail.com

---

## 📖 Table of Contents

1. [What is PhishGuard AI?](#-what-is-phishguard-ai)
2. [Key Features](#-key-features)
3. [System Architecture](#-system-architecture)
4. [How Detection Works](#-how-detection-works)
5. [Tech Stack](#-tech-stack)
6. [Project Structure](#-project-structure)
7. [Installation Guide (A → Z)](#-installation-guide-a--z)
8. [Configuration Reference](#-configuration-reference)
9. [Connecting Your Mailbox](#-connecting-your-mailbox)
10. [Real-Time Pipeline Explained](#-real-time-pipeline-explained)
11. [API Reference](#-api-reference)
12. [Testing & Maintenance](#-testing--maintenance)
13. [Docker Deployment](#-docker-deployment)
14. [Troubleshooting](#-troubleshooting)
15. [Honest Limitations](#-honest-limitations)
16. [Future Scope](#-future-scope)
17. [Author](#-author)

---

## 🔍 What is PhishGuard AI?

PhishGuard AI is a full-stack **email security platform** that:

1. **Connects directly to your real mailbox** via IMAP (Gmail, Outlook, Yahoo, Hotmail, Zoho, or any custom server).
2. **Monitors it continuously** — a background daemon polls every 15 seconds and also scans the Spam/Junk folder.
3. **Analyzes every incoming email instantly** using a hybrid engine (Machine Learning + rule-based heuristics).
4. **Pushes results live** to a premium dark-mode dashboard over WebSockets — new threats appear with a toast alert within seconds, zero manual refreshing.
5. **Explains every verdict** — each email shows a 0–100 risk score, a PHISHING / SUSPICIOUS / LEGITIMATE label, and human-readable reasons.

Built as a final-year engineering project: production-grade patterns (JWT auth, migrations, rate limiting, audit logs, Docker) combined with honest ML documentation.

---

## ✨ Key Features

### Detection Engine
| Feature | Description |
|---|---|
| 🧠 **Hybrid Scoring** | Blended verdict: `60% ML probability + 40% heuristic score` |
| 🤖 **ML Model** | TF-IDF vectorization + Logistic Regression trained on the Enron Spam corpus (`GridSearchCV` tuned) |
| 🔗 **URL Intelligence** | Extracts all links, flags unverified/TLD-suspicious domains, rewards verified ones |
| 🎭 **Brand Impersonation** | Catches display-name spoofing (`"PayPal"` on a Gmail account) and fake brand domains in links |
| ⏱️ **Urgency Phrases** | 30+ high-risk phrases (`verify your account`, `you won`, `claim your prize`…) |
| 🛡️ **Calibration Guards** | Anti-false-positive rules: free-mail senders get no trust discount; short emails with zero evidence can never be flagged by ML alone |
| 💬 **Explainable Verdicts** | Every score ships with reasons — flagged keywords, suspicious URLs, sender analysis |

### Live Monitoring
| Feature | Description |
|---|---|
| 📡 **IMAP Daemon** | Background poller every 15 s; auto-resumes after backend restart (encrypted session file) |
| 📁 **Spam-Folder Scan** | Also watches `[Gmail]/Spam`, Outlook `Junk`, Yahoo `Bulk Mail` — marks such emails with a source-folder note |
| 🔔 **WebSocket Push** | Instant `new_email` events → toast notifications + live row insert (auto-reconnect with exponential backoff) |
| ♻️ **Fallback Resync** | Silent 25 s re-sync guarantees freshness even if the socket drops |

### Platform
| Feature | Description |
|---|---|
| 🔐 **JWT Auth** | Access + refresh token rotation, password auto-sync from `.env`, rate-limited login (5/min) |
| 📜 **Audit Log** | Every sensitive action recorded (login, delete, export…) |
| 🧪 **Tested** | 45 backend pytest cases + frontend Vitest suite |
| 🐳 **Docker Ready** | Full `docker compose` dev + prod stacks with nginx |
| 🎨 **Premium UI** | Glassmorphism dark theme, account chip with connected-mailbox profile, Recharts analytics |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         YOUR REAL MAILBOX                            │
│              (Gmail / Outlook / Yahoo / Custom IMAP)                 │
│                    INBOX  +  Spam/Junk folder                        │
└──────────────┬──────────────────────────────────────────────────────┘
               │ IMAPS (TLS :993) · polled every 15s by daemon
               ▼
┌──────────────────────────────┐      ┌──────────────────────────────┐
│       FASTAPI BACKEND        │      │     DETECTION ENGINE          │
│  ─────────────────────────   │      │  ────────────────────────    │
│  · JWT auth + rate limiting  │─────▶│  TF-IDF + LogisticRegression │
│  · REST API (/inbox/*)       │      │        ↓ blend                │
│  · IMAP monitor daemon       │      │  60% ML + 40% heuristics     │
│  · Alembic migrations        │◀─────│  · URL / urgency / caps       │
│  · SQLite or PostgreSQL      │ score│  · brand impersonation        │
└──────────────┬───────────────┘      │  · calibration guards         │
               │ WebSocket push       └──────────────────────────────┘
               │ event: new_email            │
               ▼                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     REACT FRONTEND (Vite SPA)                        │
│   Threat Inbox · live toasts · account chip · analytics charts       │
│   Search/filter · custom-email scanner · audit & database views      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🧠 How Detection Works

Every email flows through a two-layer pipeline and produces a **0–100 blended risk score**:

### Layer 1 — Machine Learning (60% weight)
The cleaned text (subject + body) is vectorized with TF-IDF and passed through a Logistic Regression classifier trained on ~5,000 balanced Enron spam/ham samples. Output: phishing probability `0–100`.

### Layer 2 — Heuristics (40% weight)
| Signal | Points |
|---|---|
| Unverified/suspicious link domains | up to +30 |
| Urgency keyword hits (`+10` each) | up to +25 |
| Brand impersonation (per issue) | +25 each, cap +45 |
| Suspicious sender domain | +20 |
| ALL-CAPS abuse (>35%) | proportional |
| Punctuation abuse (!!! / ???) | proportional |

### Post-Processing Guards *(calibrated against real false positives)*
1. **Free-mail rule** — `gmail.com`, `outlook.com`, etc. never receive the −25 trusted-sender discount (anyone can open those accounts). Corporate domains (`google.com`, `amazon.in`) still qualify.
2. **Corroboration guard** — a very short email with *zero* heuristic evidence is capped at 34, so ordinary personal chatter can never be labelled SUSPICIOUS/PHISHING on ML output alone.
3. **Impersonation override** — any display-name/link-domain spoofing cancels all trust bonuses entirely.

### Final Label
| Score | Label |
|---|---|
| 0–35 | ✅ LEGITIMATE |
| 36–65 | ⚠️ SUSPICIOUS |
| 66–100 | 🚨 PHISHING |

*Verified live:* spoofed PayPal mail → **93**, prize scam → **72**, ordinary friend chat → **34**, corporate order confirmation → **29**.

---

## 💻 Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy, Alembic, Uvicorn |
| ML | scikit-learn (TF-IDF, Logistic Regression, GridSearchCV), HuggingFace datasets |
| Database | SQLite (default) / PostgreSQL (production) |
| Security | python-jose (JWT), passlib-bcrypt, slowapi rate limiting, Fernet credential encryption |
| Frontend | React 18, Vite, Tailwind CSS, Recharts, react-hot-toast, lucide-react |
| Real-Time | Native WebSockets with reconnecting client |
| DevOps | Docker Compose, nginx, GitHub Actions CI |

---

## 📂 Project Structure

```
phishguard-ai/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, routes, IMAP daemon, WS hub
│   │   ├── config.py            # Pydantic settings (.env loader)
│   │   ├── database.py          # SQLAlchemy engine/session
│   │   ├── models.py            # ORM models (EmailRecord, AdminUser…)
│   │   ├── schemas.py           # Pydantic request/response models
│   │   ├── imap_client.py       # UID-based multi-folder IMAP fetcher
│   │   ├── logger.py            # Structured logging
│   │   ├── ml/
│   │   │   ├── train_model.py   # Dataset download + training pipeline
│   │   │   ├── predict.py       # Blended scoring engine + explanations
│   │   │   └── preprocess.py    # Text cleaning, URL extraction,
│   │   │                        #   brand impersonation, trust lists
│   │   └── data/                # Demo dataset copy
│   ├── alembic/                 # DB migrations
│   ├── tests/                   # 45 pytest cases
│   ├── data/                    # phishguard.db (runtime, gitignored)
│   ├── .env.example             # Config template
│   ├── requirements.txt
│   └── reanalyze_db.py          # Re-score stored emails utility
├── frontend/
│   ├── src/
│   │   ├── pages/               # InboxView, EmailDetail, Analytics…
│   │   ├── components/          # RiskScoreBadge, ConnectButton…
│   │   └── api/client.js        # Typed fetch + reconnecting WebSocket
│   ├── package.json
│   └── vite.config.js
├── docker-compose.yml           # Dev stack
├── docker-compose.prod.yml      # Production stack (nginx)
├── start_system.bat / .sh       # One-click launcher
└── README.md
```

---

## 🚀 Installation Guide (A → Z)

### Prerequisites

| Tool | Version | Download |
|---|---|---|
| Python | 3.9+ ([add to PATH](https://www.python.org/downloads/)) | python.org |
| Node.js | 18+ | nodejs.org |
| Git | latest | git-scm.com |

### Step 1 — Clone

```bash
git clone https://github.com/virendrabamne010/phishguard-ai.git
cd phishguard-ai
```

### Step 2 — Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows   (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env         # Windows   (Linux/macOS: cp .env.example .env)
```

Open the new `.env` and set a strong `SECRET_KEY` and `ADMIN_PASSWORD`.

### Step 3 — Frontend Setup

```bash
cd ../frontend
npm install
```

### Step 4 — Run It

**Option A — One click:** double-click `start_system.bat` (Windows) or run `./start_system.sh`. Both servers open automatically; dashboard at **http://localhost:5173**.

**Option B — Manual (two terminals):**

```bash
# Terminal 1 — backend (from backend/, venv active)
uvicorn app.main:app --port 8000 --reload

# Terminal 2 — frontend (from frontend/)
npm run dev
```

### Step 5 — First Login

1. Open **http://localhost:5173** → *Go to Dashboard*
2. Login with your `ADMIN_USERNAME` / `ADMIN_PASSWORD` from `.env`
3. Click **Connect Mailbox** → choose provider → enter credentials → done!
4. Emails stream in and get analyzed live. 🎉

> On first backend startup the admin password hash is seeded/synced from `.env` automatically — changing `ADMIN_PASSWORD` takes effect after a restart.

---

## ⚙️ Configuration Reference (`backend/.env`)

| Variable | Default | Purpose |
|---|---|---|
| `ENVIRONMENT` | `development` | App mode banner |
| `SECRET_KEY` | — | JWT signing + IMAP session encryption (**must change**) |
| `ADMIN_USERNAME` | `admin` | Login username |
| `ADMIN_PASSWORD` | — | Login password (auto-synced on startup) |
| `DATABASE_URL` | SQLite path | Swap to PostgreSQL line for production |
| `FRONTEND_URL` | `http://localhost:5173` | CORS origin |
| `REDIS_URL` / OAuth vars | optional | Only needed for Gmail OAuth mode |

---

## 📬 Connecting Your Mailbox

The recommended path is **IMAP with an App Password** — works without any cloud console setup.

### Gmail
1. Google Account → **Security** → enable **2-Step Verification**
2. Search "**App passwords**" → create one (16 characters)
3. In PhishGuard: provider **Gmail**, paste email + the 16-char app password

### Outlook / Hotmail
Use your regular password (or App Password if 2FA is enabled).

### Yahoo / Zoho
Generate an App Password from account security settings first.

### What happens next
- Last 20 recent emails are fetched immediately (inbox **and** Spam folder)
- The monitor daemon keeps polling every **15 seconds**
- Session credentials are stored **encrypted (Fernet)** in `backend/imap_session.json`
- After a backend restart the daemon **auto-resumes** — no re-login needed

---

## ⚡ Real-Time Pipeline Explained

```
new mail arrives ──▶ daemon polls (≤15s) ──▶ dedupe by UID-based id
      ──▶ ML + heuristic scoring ──▶ saved to DB
      ──▶ WebSocket broadcast {event: "new_email"}
      ──▶ dashboard: toast + highlighted row appears instantly
      ──▶ {event: "stats_updated"} triggers silent list resync
```

Three safety nets guarantee liveness:
1. **WebSocket** (instant push, auto-reconnect w/ backoff)
2. **stats_updated refetch** (debounced silent refresh)
3. **25s fallback poll** (only when tab visible)

You should never need the manual *Check for new mail* action — but it's there (in the account-chip menu) when you want an immediate poll.

---

## 📚 API Reference

Interactive docs: **http://localhost:8000/docs** (Swagger UI) · alternative ReDoc at `/redoc`

| Endpoint | Method | Description |
|---|---|---|
| `/auth/login` | POST | JWT login (rate-limited 5/min) |
| `/auth/refresh` | POST | Rotate access token |
| `/auth/change-password` | POST | Change admin password |
| `/inbox/status` | GET | Mode + connected mailbox info |
| `/inbox/imap/connect` | POST | Connect mailbox, starts daemon |
| `/inbox/imap/refresh` | POST | Force immediate poll |
| `/inbox/imap/backfill?days=10` | POST | Scan history window |
| `/inbox/imap/disconnect` | POST | Stop monitoring, clear session |
| `/inbox/emails/search?q=&label=` | GET | Filtered email list |
| `/inbox/emails/{id}` | GET / DELETE | Detail / soft-delete |
| `/inbox/analyze` | POST | Scan a custom pasted email |
| `/ws?token=` | WS | Live event stream |
| `/system/analytics` | GET | Dashboard telemetry |
| `/system/export/csv·json` | GET | Authenticated report download |
| `/health` | GET | Liveness probe |

---

## 🧪 Testing & Maintenance

```bash
# Backend test suite (45 tests)
cd backend && venv\Scripts\activate && pytest -q

# Frontend tests + production build
cd frontend && npm run test -- --run && npm run build

# Retrain ML model from scratch (re-downloads Enron corpus;
# needs: pip install -r requirements-dev.txt)
python -m app.ml.train_model

# Re-score every stored email after changing detection rules
venv\Scripts\python reanalyze_db.py
```

---

## 🐳 Docker Deployment

```bash
# Development stack
docker compose up --build

# Production stack (nginx reverse proxy)
docker compose -f docker-compose.prod.yml up --build -d
```

Production checklist lives in [`DEPLOYMENT_CHECKLIST.md`](DEPLOYMENT_CHECKLIST.md).

---

## 🔧 Troubleshooting

| Symptom | Fix |
|---|---|
| Backend crashes with database error | Use SQLite line in `.env` unless PostgreSQL is running (see `.env.example`) |
| Login rejected despite correct `.env` password | Restart backend — it re-syncs the admin hash on startup |
| Gmail rejects login | You must use a **16-char App Password**, not the account password |
| New mails don't appear | Check header shows **● Live**; verify `Auto-resumed IMAP monitoring daemon` in backend logs |
| Model artifacts missing | Run `python -m app.ml.train_model` |
| Old DB missing new columns | Auto-migrates on startup; formal route: `alembic upgrade head` |

---

## ⚠️ Honest Limitations

Documented openly (examiners appreciate honesty):

- **Spam ≠ Phishing** — the ML model trains on the Enron *spam* corpus; true phishing generalization comes from the heuristic layer (URL reputation, impersonation detection, urgency analysis).
- **No SMTP-header authentication** — SPF/DKIM/DMARC are not verified; sender trust is allowlist/heuristic based.
- **Single-admin design** — one seeded account, no multi-user registration (by design for this project).
- **Polling, not IDLE** — IMAP polling every 15 s instead of push-style IMAP IDLE.
- **English-centric** — keyword lists and training data are English-only.

---

## 🔮 Future Scope

- IMAP IDLE for sub-second push delivery
- SPF/DKIM/DMARC header verification
- Fine-tuned transformer model (BERT/DistilBERT) with multilingual support
- Browser extension for webmail integration
- Multi-tenant accounts with per-user watch rules
- VirusTotal / URLhaus enrichment for link reputation

---

## 👤 Author

**Vaibhavi Nirgude**
- GitHub: [@virendrabamne010](https://github.com/virendrabamne010)
- Email: virendrabamne010@gmail.com

---

## 📄 License

Released under the MIT License. Educational project — see `LICENSE` for details.

<div align="center">Built with ❤️ for safer inboxes</div>
