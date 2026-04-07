# MSRIT Attendance Monitoring System

An end-to-end attendance monitoring system for **Ramaiah Institute of Technology**.
Scrapes proctored student attendance from the staff portal, stores it in PostgreSQL, sends email alerts to teachers and students, and presents everything through a React dashboard.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                                                                 │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────────┐  │
│  │   Scraper    │───▶│  Backend API     │◀───│  Frontend    │  │
│  │  (Selenium)  │    │  FastAPI :8000   │    │  React :5173 │  │
│  └──────────────┘    └────────┬─────────┘    └──────────────┘  │
│         │                     │                                 │
│         ▼                     ▼                                 │
│  ┌──────────────┐    ┌──────────────────┐                      │
│  │  PostgreSQL  │    │  Notification    │                      │
│  │     DB       │    │  Service :8001   │──▶ Gmail SMTP        │
│  └──────────────┘    └──────────────────┘                      │
└─────────────────────────────────────────────────────────────────┘
```

| Component | Location | Port | Description |
|-----------|----------|------|-------------|
| Scraper | `msrit-scraper/app/` | — | Selenium scraper, runs manually or on schedule |
| Backend API | `msrit-scraper/backend/` | 8000 | FastAPI — exposes attendance data + triggers alerts |
| Notification Service | `notification-service/` | 8001 | FastAPI microservice — sends HTML emails via Gmail SMTP |
| Frontend | `frontend/` | 5173 | React + Vite dashboard |
| Database | PostgreSQL | 5432 | Single shared DB for all services |

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.10+ | 3.13 recommended |
| Node.js | 18+ | via `nvm` recommended |
| PostgreSQL | 14+ | Must be running locally |
| Google Chrome | Latest | Required by Selenium scraper |
| Gmail account | — | With 2FA + App Password for SMTP |

> **College LAN required** — the staff portal (`staff.msrit.edu`) is only accessible on the college network or VPN. The scraper will fail outside it. All other services (backend, notification, frontend) work anywhere.

---

## Project Structure

```
devops/
├── .gitignore
├── README.md
│
├── msrit-scraper/               # Scraper + Backend API
│   ├── app/                     # Phase 1 — Selenium scraper
│   │   ├── config.py
│   │   ├── scraper.py           # Chrome WebDriver setup
│   │   ├── login.py             # Portal login automation
│   │   ├── proctorship.py       # Student list extraction
│   │   ├── attendance.py        # Attendance table parser
│   │   ├── db.py                # psycopg2 DB writes
│   │   ├── encryption.py        # Fernet AES password encryption
│   │   └── main.py              # Entry point
│   │
│   ├── backend/                 # Phase 2/4 — FastAPI REST API
│   │   ├── main.py              # App startup + CSV email sync
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   ├── schemas.py           # Pydantic response schemas
│   │   ├── crud.py              # DB query logic
│   │   ├── database.py          # SQLAlchemy engine + session
│   │   ├── notify_client.py     # HTTP client to notification service
│   │   ├── config.py
│   │   ├── routers/
│   │   │   ├── teachers.py
│   │   │   ├── students.py
│   │   │   ├── attendance.py
│   │   │   ├── alerts.py        # POST /alerts/send/{teacher_id}
│   │   │   └── health.py
│   │   └── scripts/
│   │       └── import_emails.py # CLI — bulk load emails.csv into DB
│   │
│   ├── scripts/
│   │   ├── add_teacher.py       # CLI — add a teacher + encrypt password
│   │   └── generate_fernet_key.py
│   │
│   ├── emails.csv               # USN→Email map (gitignored — you create this)
│   ├── requirements.txt
│   ├── .env                     # gitignored
│   ├── .env.example             # ← copy this to .env and fill in values
│   └── test_phase6.py           # End-to-end smoke test
│
├── notification-service/        # Phase 3 — Email microservice
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py          # alert_logs table setup
│   │   ├── models.py            # AlertLog ORM
│   │   ├── schemas.py           # NotifyRequest / NotifyResponse
│   │   ├── email_service.py     # Teacher summary + student personal emails
│   │   ├── logger.py
│   │   └── routes/
│   │       └── notify.py        # POST /notify, GET /alerts/logs
│   ├── requirements.txt
│   ├── .env                     # gitignored
│   └── .env.example
│
└── frontend/                    # Phase 5 — React dashboard
    ├── src/
    │   ├── App.jsx
    │   ├── App.css
    │   ├── api/index.js          # All API calls
    │   ├── context/ToastContext.jsx
    │   ├── components/
    │   │   ├── Navbar.jsx
    │   │   ├── TeacherCard.jsx
    │   │   ├── StudentTable.jsx
    │   │   └── LogsTable.jsx
    │   └── pages/
    │       ├── Dashboard.jsx     # Stats + teacher grid + notify checkboxes
    │       └── Logs.jsx          # Alert log history with filters
    ├── package.json
    ├── vite.config.js
    ├── .env                      # gitignored
    └── .env.example
```

---

## First-Time Setup

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/msrit-attendance.git
cd msrit-attendance
```

### 2. Create the PostgreSQL database

```bash
psql -U $(whoami) -c "CREATE DATABASE msrit_attendance;"
```

### 3. Set up the scraper + backend

```bash
cd msrit-scraper

# Install Python dependencies
pip3 install -r requirements.txt

# Copy env template and fill in your values
cp .env.example .env
```

Open `.env` and set:

| Variable | What to put |
|----------|-------------|
| `DB_USER` | Your macOS username (run `whoami` to find it) |
| `DB_PASSWORD` | Leave blank if no PostgreSQL password |
| `FERNET_KEY` | Run `python3 scripts/generate_fernet_key.py` — copy the output |
| `SMTP_USER` | Your Gmail address |
| `SMTP_PASSWORD` | Gmail App Password (see section below) |
| `ALERT_SENDER` | Same as `SMTP_USER` |

> **Fernet key warning** — generate it once and never change it. If you regenerate it after adding teachers, their encrypted portal passwords become unreadable and you will have to re-add them.

### 4. Add teachers to the database

```bash
# Run from msrit-scraper/
python3 scripts/add_teacher.py
```

You will be prompted for:
- Teacher name
- Teacher email (where alerts are sent)
- Portal username (staff portal login)
- Portal password (encrypted with Fernet before storing — never stored in plain text)

Repeat for each teacher.

### 5. Set up the notification service

```bash
cd ../notification-service
pip3 install -r requirements.txt

cp .env.example .env
# Fill in the same SMTP and DB values as msrit-scraper/.env
```

### 6. Set up the frontend

```bash
cd ../frontend

# Install Node dependencies (use nvm if npm is not in PATH)
source ~/.nvm/nvm.sh
npm install

cp .env.example .env
# Default value is fine for local development:
# VITE_API_BASE_URL=http://localhost:8000
```

---

## Gmail App Password Setup

Standard Gmail passwords do not work with SMTP. You need an **App Password**:

1. Go to [myaccount.google.com](https://myaccount.google.com)
2. **Security** → **2-Step Verification** → enable it if not already on
3. Search for **App Passwords** at the top
4. Select app: **Mail** / device: **Mac** → click **Generate**
5. Copy the 16-character password (no spaces) into `SMTP_PASSWORD` in your `.env` files

---

## Running the System

Open **three separate terminals**:

**Terminal 1 — Backend API**
```bash
cd ~/Desktop/devops/msrit-scraper
python3 -m uvicorn backend.main:app --port 8000 --reload
```

**Terminal 2 — Notification Service**
```bash
cd ~/Desktop/devops/notification-service
python3 -m uvicorn app.main:app --port 8001 --reload
```

**Terminal 3 — Frontend**
```bash
source ~/.nvm/nvm.sh
cd ~/Desktop/devops/frontend
npm run dev
```

Then open **http://localhost:5173** in your browser.

---

## Running the Scraper

> Must be on **college LAN or VPN** — the staff portal is not accessible from outside.

```bash
cd ~/Desktop/devops/msrit-scraper
python3 -m app.main
```

The scraper will:
1. Loop through every teacher in the database
2. Log into the staff portal with their credentials
3. Navigate to the proctorship page
4. Extract attendance data for each student
5. Save everything to PostgreSQL

Run this once per day (or after each portal update) to keep data fresh.

---

## Student Email Setup (Phase 6)

Student emails are loaded from a CSV file — **not scraped** from the portal.

### Create `emails.csv`

```bash
# File goes in msrit-scraper/ directory
cat > emails.csv << 'EOF'
USN,Email
1MS23CS001,student1@gmail.com
1MS23CS002,student2@gmail.com
1MS23CS003,student3@gmail.com
EOF
```

### Sync to database

Emails are **automatically synced every time the backend starts**. Or sync manually:

```bash
cd msrit-scraper
python3 -m backend.scripts.import_emails --csv emails.csv

# Preview without writing to DB
python3 -m backend.scripts.import_emails --csv emails.csv --dry-run
```

---

## Sending Alerts

From the **Dashboard** in the frontend:

1. Select which notifications to send using the checkboxes:
   - **Teacher (summary)** — one email to the teacher listing all low-attendance students
   - **Students (personalized)** — individual email to each student with their own subjects
2. Click a teacher card to view their low-attendance students
3. Click **Send Alert** on the teacher card

Alerts are only sent for students whose attendance is **below 75%** (configurable via `ATTENDANCE_THRESHOLD`).

---

## API Reference

### Backend API — http://localhost:8000

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health + DB status |
| GET | `/teachers` | List all teachers |
| GET | `/teachers/{id}` | Single teacher |
| GET | `/students` | List all students |
| GET | `/students/{usn}` | Single student by USN |
| GET | `/attendance/{usn}` | Latest attendance records for a student |
| GET | `/low-attendance` | Students below attendance threshold |
| GET | `/summary` | Dashboard statistics |
| POST | `/alerts/send/{teacher_id}` | Send alert emails |
| GET | `/alerts/logs` | Alert log history (proxied from notification service) |

**POST `/alerts/send/{teacher_id}` body:**
```json
{
  "notify_teacher": true,
  "notify_student": true
}
```

### Notification Service — http://localhost:8001

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/notify` | Send alert emails |
| GET | `/alerts/logs` | Query alert log history |

---

## Interactive API Docs

Both services expose Swagger UI automatically:

- Backend: http://localhost:8000/docs
- Notification Service: http://localhost:8001/docs

---

## College LAN Access

To access the dashboard from **any device on the college network**:

1. Find your machine's IP:
   ```bash
   ipconfig getifaddr en0
   # e.g. 192.168.1.42
   ```

2. Update `frontend/.env`:
   ```
   VITE_API_BASE_URL=http://192.168.1.42:8000
   ```

3. Restart the frontend (`npm run dev`)

4. Other devices on the LAN can now open:
   - Dashboard: `http://192.168.1.42:5173`
   - API: `http://192.168.1.42:8000/docs`

---

## Running the Test Suite

Verify every Phase 6 feature is wired up correctly:

```bash
cd ~/Desktop/devops/msrit-scraper

# Structure + schema tests only
python3 test_phase6.py

# Include a live student email delivery test (sends a real email)
python3 test_phase6.py --student-email you@gmail.com
```

The test covers:
- Both services are reachable
- `student_email` field present in `/low-attendance` response
- `notify_teacher` / `notify_student` flags accepted by backend
- Notification service schema validation (graceful skip when no email, 400 when both flags false)
- Live SMTP delivery to a real student email address (with `--student-email`)
- `recipient_type` column (`teacher` / `student`) present in alert logs
- `emails.csv` exists and `import_emails.py --dry-run` works

---

## Security Notes

| What | How it's protected |
|------|--------------------|
| Portal passwords | Encrypted with **Fernet AES-128-CBC** before storing in DB. Decrypted only in memory during scrape. Never logged or returned by any API. |
| Gmail App Password | Stored in `.env` only. Gitignored. Never hardcoded. |
| Fernet key | Stored in `.env`. Gitignored. Generate once — losing it means re-adding all teachers. |
| Student emails | Stored in `emails.csv` locally. Gitignored (PII). |
| API responses | `portal_password_encrypted` is structurally absent from all ORM schemas. |

---

## Troubleshooting

**`python` command not found**
```bash
# Use python3 explicitly
python3 -m uvicorn backend.main:app --port 8000 --reload
```

**`npm` not found**
```bash
source ~/.nvm/nvm.sh
npm run dev
```

**`ModuleNotFoundError: No module named 'backend'`**
```bash
# Must run from msrit-scraper/ directory, not devops/
cd ~/Desktop/devops/msrit-scraper
python3 -m uvicorn backend.main:app --port 8000 --reload
```

**Port already in use**
```bash
kill $(lsof -ti:8000)   # backend
kill $(lsof -ti:8001)   # notification service
kill $(lsof -ti:5173)   # frontend
```

**Scraper login fails**
- You must be on college LAN or VPN
- Verify portal username/password with `psql` → `SELECT portal_username FROM teachers;`
- Re-add the teacher with `python3 scripts/add_teacher.py` if credentials changed

**No low-attendance students showing in dashboard**
- Run the scraper first (on college LAN)
- Check the threshold: default is 75%. Query the DB: `SELECT COUNT(*) FROM attendance_records;`

**Emails not sending**
- Verify Gmail 2FA is enabled and App Password is correct (16 chars, no spaces)
- Test SMTP directly: `python3 -c "import smtplib; s=smtplib.SMTP('smtp.gmail.com',587); s.starttls(); s.login('you@gmail.com','apppassword'); print('OK')"`

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Scraper | Python 3.13, Selenium 4, webdriver-manager |
| Password encryption | `cryptography` — Fernet (AES-128-CBC + HMAC-SHA256) |
| Backend API | FastAPI, SQLAlchemy 2.0, Pydantic v2, Uvicorn |
| Notification service | FastAPI, smtplib, Gmail SMTP TLS |
| HTTP between services | httpx (async-capable, retry logic) |
| Database | PostgreSQL 14+, psycopg2 |
| Frontend | React 18, Vite 5, react-router-dom v6 |
| Styling | Pure CSS (no UI framework) — MSRIT navy `#1a237e` theme |
