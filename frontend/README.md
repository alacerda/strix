# Strix Frontend

Next.js frontend for Strix web interface.

## Development

### Prerequisites

- Node.js 18+ 
- npm or yarn

### Installation

```bash
npm install
```

### Run in development mode

```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`.

### Build for production

```bash
npm run build
```

The build will be generated in `.next/`. The Python backend will automatically serve the build when available.

## Structure

- `src/app/` - Next.js Pages (App Router)
- `src/components/` - React Components
- `src/hooks/` - Custom Hooks
- `src/lib/` - Utilities (API client, WebSocket)
- `src/types/` - TypeScript Definitions

## Backend Integration

The frontend connects to the Python FastAPI backend via:
- REST API at `/api/*`
- WebSocket at `/ws`

Requests are redirected via `next.config.js` to the backend at `http://127.0.0.1:8080`.

