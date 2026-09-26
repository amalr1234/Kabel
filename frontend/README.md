# SOLVIA Frontend

Dark enterprise React UI for the SOLVIA intelligent solution discovery engine.

## Prerequisites

- Node.js 18+ and npm 9+
- Backend running at `http://localhost:8000` (see backend README)

## Setup

```bash
cd frontend

# Install dependencies
npm install

# Copy environment
cp .env.example .env.local
# Edit NEXT_PUBLIC_API_URL if your backend is hosted elsewhere
```

## Development

```bash
npm run dev
```

Frontend: `http://localhost:3000`

## Build

```bash
npm run build
npm start
```

## Environment variables

| Variable | Purpose |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | Base URL for the SOLVIA backend API |

## Architecture

- Next.js 15 app (pages router)
- TypeScript
- Tailwind CSS with minimal dark enterprise theme
- Typed API client in `src/lib/api.ts`
- Pages: `/search`, `/feedback`, `/audit`, `/analytics`
