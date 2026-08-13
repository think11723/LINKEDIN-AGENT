# LinkedIn AI Studio — Frontend

React + Vite + JavaScript + Tailwind CSS frontend for the LinkedIn Content Agent backend.

## Scripts

```bash
npm install
npm run dev      # start Vite dev server
npm run build    # build for production
npm run preview  # preview the production build
```

## Environment

Copy `.env.example` to `.env` and provide public Firebase Web SDK credentials plus the
backend base URL. Never place backend secrets here — they will be exposed to the browser.

| Variable                       | Purpose                                              |
| ------------------------------ | ---------------------------------------------------- |
| `VITE_API_BASE_URL`            | FastAPI backend (default `http://localhost:8000`).   |
| `VITE_FIREBASE_API_KEY`        | Firebase Web SDK key.                                |
| `VITE_FIREBASE_AUTH_DOMAIN`    | Firebase auth domain.                                |
| `VITE_FIREBASE_PROJECT_ID`     | Firebase project id.                                 |
| `VITE_FIREBASE_STORAGE_BUCKET` | Firebase storage bucket.                             |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | Firebase messaging sender id.                   |
| `VITE_FIREBASE_APP_ID`         | Firebase app id.                                     |

## Architecture

```
src/
  components/   # reusable UI primitives (Button, Card, Badge, Input, Feedback)
  context/      # Auth, Toast, Drafts providers
  layouts/      # AppShell with sidebar + topbar
  pages/        # route components
  services/     # Firebase init, API client (Firebase ID token attached)
  utils/        # cn() helper, date helpers
```

The API client attaches the Firebase ID token to every backend request as
`Authorization: Bearer <token>` and exposes typed wrappers for each FastAPI route
(`/api/v1/dashboard`, `/api/v1/content`, `/api/v1/approval`, `/api/v1/scheduler`,
`/api/v1/activity`). The backend is not modified by this frontend.