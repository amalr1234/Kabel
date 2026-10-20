# SOLVIA Backend (FastAPI)

## Quick start (local development)

```bash
cd backend

# First time only: create .venv and install dependencies
npm run setup

# Run the server with auto-reload on code changes
npm run dev

# Or run without auto-reload
npm run start
```

Optional: set `DEMO_MODE=true` in `backend/.env` to run without a Gemini API key.

- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

## Environment

| Variable | Purpose |
| --- | --- |
| `GEMINI_API_KEY` | Google Gemini API key (never expose to frontend) |
| `GEMINI_MODEL` | Generation model (default `gemini-2.0-flash`) |
| `GEMINI_EMBEDDING_MODEL` | Embedding model (default `gemini-embedding-001`) |
| `DEMO_MODE` | When `true`, backend runs without a real Gemini key |
| `CHROMA_PERSIST_DIRECTORY` | Local ChromaDB storage directory |
| `DATABASE_URL` | PostgreSQL connection string |
| `SOLVIA_DB_SQLITE` | Set to `1` to use SQLite for local dev |

## Frontend

The frontend is in `../frontend`. a

```bash
cd ../frontend
npm install
cp .env.example .env.local   # edit NEXT_PUBLIC_API_URL if needed
npm run dev                  # http://localhost:3000
```

Local development URLs:
- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

## API endpoints

- `GET /health` — health check
- `GET /tickets` — list tickets
- `GET /tickets/{ticket_id}` — get ticket
- `POST /tickets` — create ticket
- `GET /documents` — list documents
- `GET /documents/{document_id}` — get document
- `POST /documents` — create document
- `POST /feedback` — record feedback
- `GET /feedback/solution/{solution_id}` — feedback for a solution
- `POST /audit` — create audit event
- `GET /audit` — list audit events
