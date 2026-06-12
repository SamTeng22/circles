# Circles

Study together. Quiz together.

## Stack

**Frontend**: Next.js 14 + TypeScript + Tailwind + Firebase Auth  
**Backend**: FastAPI + PostgreSQL + pgvector + Gemini 1.5 Flash  
**Deploy**: Vercel (frontend) + Railway (backend)

---

## Local setup

### 1. PostgreSQL + pgvector

```bash
# Make sure pgvector is installed
# Then create the database
createdb circles
```

### 2. Backend

```bash
cd circles-backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Fill in your .env values

uvicorn app.main:app --reload
# Runs on http://localhost:8000
```

### 3. Frontend

```bash
cd circles-frontend
npm install

cp .env.example .env.local
# Fill in your Firebase config

npm run dev
# Runs on http://localhost:3000
```

---

## Firebase setup

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Create a new project
3. Enable **Google sign-in** under Authentication
4. Copy your web app config into `.env.local`
5. In Firebase Console → Project Settings → Service Accounts → Generate new private key
6. Set `GOOGLE_APPLICATION_CREDENTIALS` env variable to the path of that JSON file (backend uses this for token verification)

---

## Deploy

### Railway (backend)
- Connect your GitHub repo
- Set environment variables from `.env.example`
- Railway auto-detects the `Procfile`

### Vercel (frontend)
- Connect your GitHub repo
- Set environment variables from `.env.example`
- Set `NEXT_PUBLIC_API_URL` to your Railway backend URL

---

## Project structure

```
circles/
├── circles-backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── core/
│   │   │   ├── config.py        # Settings / env vars
│   │   │   └── firebase.py      # Auth dependency
│   │   ├── db/
│   │   │   └── database.py      # DB pool + schema init
│   │   ├── api/routes/
│   │   │   ├── auth.py          # /api/auth
│   │   │   ├── circles.py       # /api/circles
│   │   │   ├── notes.py         # /api/notes
│   │   │   ├── quiz.py          # /api/quiz
│   │   │   └── live.py          # WebSocket /api/live/ws
│   │   └── services/
│   │       ├── embedding.py     # Chunking + pgvector
│   │       └── quiz_generator.py # RAG + Gemini
│   ├── requirements.txt
│   └── Procfile
│
└── circles-frontend/
    ├── src/
    │   ├── app/
    │   │   ├── layout.tsx
    │   │   ├── page.tsx          # Login
    │   │   └── dashboard/page.tsx # Circles list
    │   └── lib/
    │       ├── firebase.ts       # Firebase init + helpers
    │       ├── api.ts            # API client + types
    │       └── AuthContext.tsx   # Auth provider
    └── package.json
```

## What's next

- [ ] `/circles/[id]` — circle detail page (notes, quizzes, members)
- [ ] Notes upload UI with react-dropzone
- [ ] Quiz generation UI
- [ ] Conflict detection service
- [ ] Live quiz room with WebSocket
- [ ] Scoreboard
