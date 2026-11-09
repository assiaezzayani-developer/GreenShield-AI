# GreenShield AI — full-stack functional project

React/Vite frontend + FastAPI backend + SQLite database. Features include user registration/login (PBKDF2 password hashing, signed 14-day sessions), per-user plant CRUD, real image uploads, care tasks with repeat schedules, health passport timeline and treatment logging, recovery before/after records, dashboard metrics, rule-based schedule recommendations, and NVIDIA image diagnosis when a valid API key and image-compatible model are available. UI has six selectable languages; some feature-specific microcopy remains English. Plans are illustrative and PayPal checkout is intentionally disabled.

## Requirements
- Python 3.10+ and Node.js 20+

## Run backend
```bash
cd backend
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env  # Windows: copy .env.example .env
# edit .env, use a unique APP_SECRET and your own NVIDIA_API_KEY
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```
Open http://localhost:8000/docs for interactive API documentation.

## Run frontend (second terminal)
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173 . Optionally create frontend/.env with `VITE_API_URL=http://localhost:8000`.

## Test workflow
1. Register a new account, then add a plant with a photo.
2. Schedule a recurring watering task; mark it complete and observe the next scheduled occurrence.
3. Open Health Passport and log a treatment; check the dashboard.
4. Upload before and after photos to Recovery Tracker.
5. Configure NVIDIA_API_KEY and use Plant Doctor to analyze a real plant photo; linked diagnoses are saved to the passport.
6. Log out and sign in again; all records persist in `backend/greenshield.db`.

## Important limitations / production checklist
- NVIDIA API call requires your own key, credits and a model that supports the submitted image message schema. The supplied Nemotron model identifier has **not** been independently verified for image input; if the provider rejects images, set `NVIDIA_MODEL` to a confirmed vision-capable model. Errors are shown, not replaced by fabricated diagnoses.
- AI Recommendations page uses real task-derived rule-based recommendations; AI-powered personalized recommendations are not implemented as a separate endpoint.
- PayPal is **disabled**: no checkout, billing, subscription provisioning, or plan enforcement exists.
- For public deployment, add HTTPS, a secure hosting configuration, rate limits, CSRF/security review, email verification/password reset, backup policy, object storage with authorization for private images, privacy policy and consent, observability, and automated tests. Uploaded photos are currently publicly reachable by opaque URL; avoid sensitive images.
- Change `APP_SECRET` for production. Do not commit `.env`, `.db`, or `uploads/`.
