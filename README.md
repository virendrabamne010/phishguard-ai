# PhishGuard AI: Comprehensive Project Guide

Welcome to **PhishGuard AI**, a full-stack, enterprise-grade phishing detection platform. This document serves as the complete "A to Z" guide for understanding what this project is, how it was built, and how to run it on any machine from scratch.

---

## 📖 Part 1: What We Did & How We Did It (A to Z)

### The Problem
Phishing attacks are becoming increasingly sophisticated, bypassing traditional email spam filters. Our goal was to create a modern, AI-driven system that not only detects phishing emails but also *explains why* they are dangerous, providing real-time telemetry to administrators.

### The Architecture (How we did it)
We divided the project into four core components to ensure scalability and performance:

1. **The Machine Learning Engine (The Brain) 🧠**
   - **What we did:** We trained an AI model to classify emails as Legitimate, Suspicious, or Phishing.
   - **How we did it:** We used `scikit-learn` in Python. We downloaded the massive **Enron Spam Corpus**, cleaned the text, and used **TF-IDF (Term Frequency-Inverse Document Frequency)** to convert text into mathematical vectors. We then trained a **Logistic Regression** model and tuned it using `GridSearchCV` for maximum accuracy. To prevent false alarms on real work emails, we built a hardcoded "Trusted Allowlist" of 80+ safe domains.

2. **The Backend API (The Engine) ⚙️**
   - **What we did:** We built a secure server to handle database operations, user authentication, and email fetching.
   - **How we did it:** We used **FastAPI** (Python) for ultra-fast, asynchronous API endpoints. We integrated standard **IMAP protocols** so the system can connect directly to Gmail, Outlook, or Yahoo to read incoming emails. We used **SQLAlchemy** to store data in a SQLite/PostgreSQL database and secured the admin login with **JWT (JSON Web Tokens)**.

3. **The Frontend Dashboard (The Face) 🎨**
   - **What we did:** We created a premium, dark-mode SaaS dashboard for administrators to view threats and system health.
   - **How we did it:** We built a Single Page Application (SPA) using **React.js** and **Vite**. For styling, we used **Tailwind CSS** to achieve a "Glassmorphism" aesthetic. We used **Recharts** for drawing the beautiful telemetry graphs and **WebSockets** so the dashboard updates instantly without refreshing the page.

4. **Deployment & Operations (The Infrastructure) 🚀**
   - **What we did:** We made the project easy to run on any computer.
   - **How we did it:** We wrote custom batch (`.bat`) and shell (`.sh`) scripts that automatically launch both the frontend and backend with a single click. For production environments, we also containerized everything using **Docker Compose**.

---

## ✨ Part 2: Key Features Included

- **Explainable AI:** The model doesn't just give a risk score; it highlights the exact suspicious keywords found in the email.
- **Real-Time WebSockets:** See live connection status and instant threat alerts.
- **Multi-Provider IMAP:** Connects securely to almost any email provider.
- **Encrypted Session Persistence:** Saved email credentials are encrypted at rest for security.
- **Premium UI:** Built with `Inter` typography, `lucide-react` icons, and smooth micro-animations.

---

## 🛠️ Part 3: Step-by-Step Installation Guide (For ZIP Sharing)

If you have received this project as a `.zip` file, follow these exact steps to run it on your Windows PC.

### Prerequisites (What you need installed on your PC)
Before starting, ensure you have the following installed on your computer:
1. **Python (3.9 or higher):** [Download Python](https://www.python.org/downloads/) (Make sure to check the box "Add Python to PATH" during installation).
2. **Node.js (v18 or higher):** [Download Node.js](https://nodejs.org/) (This installs `npm`, which is required for the frontend).

### Step 1: Unzip the Project
Extract the `.zip` file into a folder on your computer (e.g., `Desktop/PhishGuard-AI`).

### Step 2: First-Time Setup (Terminal Commands)
Open a terminal (Command Prompt or PowerShell) inside the extracted project folder and run the following commands to install the dependencies:

**A. Setup the Backend:**
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
cd ..
```

> The launcher script (`start_system.bat`) automatically detects either a `venv` or `.venv-1` folder inside `backend/`, so either name works.

**B. Setup the Frontend:**
```bash
cd frontend
npm install
cd ..
```

### Step 3: Start the System (One-Click)
Once the setup is complete, you no longer need to type long commands. 
Simply double-click the **`start_system.bat`** file located in the main project folder.

- A terminal window will open to start the FastAPI backend.
- A second terminal window will open to start the React frontend.
- Your default web browser will automatically open to `http://localhost:5173`.

### Step 4: Login and Usage
1. On the landing page, click **"Go to Dashboard"**.
2. **Login Credentials** (configured in `backend/.env`):
   - **Username:** `ADMIN_USERNAME` (default: `admin`)
   - **Password:** `ADMIN_PASSWORD` (default in the shipped `.env`: `PhishGuard@2025!`)
   - The backend automatically keeps the stored admin password in sync with
     `.env` on every startup — changing `ADMIN_PASSWORD` takes effect on restart.
3. Once logged in, navigate to the **Inbox** tab to connect an email address via IMAP and watch the AI scan emails in real-time!

---

## ⚠️ Honest Limitations (for the viva/report)

- **Spam ≠ Phishing:** The model is trained on the **Enron Spam corpus**
  (`SetFit/enron_spam` via HuggingFace), which is mostly *spam* (marketing,
  chain letters). Real phishing generalization is boosted by the heuristic
  layer (URL reputation, urgency phrases, sender analysis, brand-impersonation
  detection) rather than the ML model alone. State this openly in the report —
  examiners value honesty.
- **Calibration guards (added after live testing):** the blended score uses
  three anti-false-positive rules — (1) free-mail providers (`gmail.com`,
  `outlook.com`, …) never receive the trusted-sender discount since anyone can
  open such accounts; (2) a very short email with *zero* heuristic evidence is
  capped below the suspicious band so ordinary personal chatter cannot be
  flagged by the ML score alone; (3) brand impersonation (display-name vs link
  domain mismatch) suppresses trust bonuses entirely.
- **Single-admin auth:** There is one admin account seeded from `.env`;
  there is no user registration flow by design.
- **Header-based detection only:** The system does not verify SPF/DKIM/DMARC
  records; sender trust is allowlist/heuristic based.

---

## 🧪 Testing & Development

If you want to run automated tests or regenerate the AI model from scratch:

**Regenerate Machine Learning Model:**
```bash
cd backend
venv\Scripts\activate
python -m app.ml.train_model
```
*(This will re-download the Enron dataset and retrain the Logistic Regression model).*

**Run Backend Tests:**
```bash
cd backend
venv\Scripts\activate
pytest -q
```

**Re-score Existing Emails (after changing detection rules):**
```bash
cd backend
venv\Scripts\python reanalyze_db.py
```
*(Re-runs the detector over every stored email and refreshes scores/labels/reasons.)*

**Run via Docker (Optional):**
If you have Docker Desktop installed, you can skip the manual setup entirely:
```bash
docker compose up --build
```

---

## 🔧 Troubleshooting

| Symptom | Fix |
|---|---|
| Backend crashes on startup with a database connection error | `backend/.env` ships pointed at local PostgreSQL. If Postgres isn't running, comment the `DATABASE_URL=postgresql://...` line and uncomment `DATABASE_URL=sqlite:///./data/phishguard.db` |
| Login rejected even though `.env` password is correct | Restart the backend — it re-syncs the admin hash from `ADMIN_PASSWORD` on startup |
| Old database missing new columns | The app auto-migrates missing columns on startup. For formal migration management use `alembic upgrade head` from `backend/` |
| Model artifacts missing | Regenerate: `python -m app.ml.train_model` (requires `pip install -r requirements-dev.txt` for dataset download) |

---
*Built with ❤️ for advanced email security.*
