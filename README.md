# Code Mentor — Python A-to-Z Learning & AI Code Assistant

A Flask + SQLite web app that teaches Python step-by-step (A to Z) and provides a
free AI-powered "Explain My Code" dashboard plus a two-style code comparison tool.

## Features
- **A-to-Z Python curriculum** — 30+ guided lessons (variables → OOP → projects)
- **Explain My Code** — paste any Python code and get a step-by-step meaning + syntax
- **Compare Styles** — see two different styles (procedural vs modern) of the same program
- **Free LLM integration** — works with Groq's free model, no API key needed (falls back to offline mode)
- **Admin/User roles** — admin manages lessons, users, and content
- Persistent progress tracking per user

## Tech Stack
- Python **Flask** + **SQLAlchemy** + **SQLite**
- Deployable to **Vercel** (`vercel.json` included)
- Free LLM via Groq (optional `GROQ_API_KEY` raises rate limits)

## Run Locally
```bash
pip install -r requirements.txt
python app.py
```
Open http://localhost:5000

## First admin account
After `python app.py`, register a normal account, then in a Python shell promote it:
```python
python
>>> from app import app
>>> from models import db, User
>>> with app.app_context():
...     u = User.query.filter_by(username="yourname").first()
...     u.role = "admin"
...     db.session.commit()
```
Or simply create the initial admin by editing the first registered user's role.

## Deploy to Vercel
1. Push this repo to GitHub
2. Import it in Vercel
3. Framework preset: **Other** (or Python)
4. Build command: `pip install -r requirements.txt`
5. Deploy. (Note: SQLite file storage is ephemeral on Vercel's serverless — for persistence, connect a Postgres via DATABASE_URL.)
