# Frontend Specification

## Stack
- React 18 + TypeScript
- Vite 5 with vite-plugin-pwa
- Tailwind CSS v3
- TanStack Query v5 (React Query)
- Zustand for auth/local state
- React Router v6
- amazon-cognito-identity-js (direct Cognito auth, no Amplify)
- date-fns for date formatting/timezone handling
- lucide-react for icons

---

## PWA Configuration
`vite.config.ts` must include `vite-plugin-pwa` with:
- `registerType: 'autoUpdate'`
- `manifest` with `display: 'standalone'`, `theme_color`, `background_color`
- App icons at 192x192 and 512x512 in `public/icons/`
- Precache strategy for static assets
- Network-first strategy for API calls

`public/manifest.json`:
```json
{
  "name": "World Cup Predictions",
  "short_name": "WC Picks",
  "display": "standalone",
  "start_url": "/",
  "theme_color": "#10b981",
  "background_color": "#111827",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

---

## Routing (`src/App.tsx`)

```
/                   → redirect to /tournaments or /login
/login              → LoginPage
/register           → RegisterPage
/verify             → EmailVerificationPage
/forgot-password    → ForgotPasswordPage

/tournaments        → TournamentsPage (list)
/tournaments/:id    → TournamentPage (matches grouped by stage/matchday)
/predictions        → MyPredictionsPage (all my picks, filterable)
/leaderboard        → GlobalLeaderboardPage
/parties            → PartiesPage (my parties list)
/parties/create     → CreatePartyPage
/parties/join/:code → JoinPartyPage (shows party preview + join button)
/parties/:id        → PartyPage (members + party leaderboard)
/profile            → ProfilePage
```

Protected routes: all except `/login`, `/register`, `/verify`, `/forgot-password`, `/parties/join/:code`.

---

## Auth (`src/lib/auth.ts` + `src/stores/authStore.ts`)

### Zustand store shape:
```typescript
interface AuthState {
  user: CognitoUser | null;
  tokens: { accessToken: string; idToken: string; refreshToken: string } | null;
  isLoading: boolean;
  login: (usernameOrEmail: string, password: string) => Promise<void>;
  logout: () => void;
  refreshTokens: () => Promise<void>;
}
```

### API client (`src/lib/apiClient.ts`):
- Axios instance with `baseURL` from `VITE_API_BASE_URL` env var
- Request interceptor: attach `Authorization: Bearer {idToken}` header
- Response interceptor: on 401, attempt token refresh, retry once, then redirect to `/login`

---

## Pages

### `TournamentPage`
Main game page. Shows matches grouped by stage, then by match day.

For each match, renders a `MatchCard`.

Top section: quick stats (my points, rank in global party, predictions made/total).

### `MatchCard` Component
Most important component. Two states:

**Editable (match not started):**
- Team flags/names, kickoff date/time (in user's local timezone)
- Countdown timer (e.g., "Locks in 2h 34m")
- Score inputs: `[🇧🇷 Brazil] [2] — [1] [🇦🇷 Argentina]`
- Save button (disabled if unchanged)
- Optimistic update on save — show spinner briefly

**Locked (match started or finished):**
- If finished: show actual score prominently, user's prediction, points earned (badge: "+5 pts" or "+2 pts" or "0 pts")
- If live: show "LIVE" badge + current score if available
- If started but not finished: show "In Progress" + user's locked prediction

### `LeaderboardTable` Component
| Rank | User | Points | Exact Scores | Predictions |
- Highlight current user's row
- Rank delta indicator (▲2, ▼1, —)
- Pagination: 50 per page

### `MyPredictionsPage`
Grid of all matches with prediction status:
- ✅ Predicted (with score)
- ⏰ Pending (match not started, no prediction yet)
- 🔒 Locked (started, no prediction made — 0 pts guaranteed)
- ✨ Scored (finished, shows points)

Filter tabs: All | Group Stage | Knockout | Pending | Scored

---

## API Hooks (`src/hooks/`)

Use TanStack Query. All hooks pattern:
```typescript
// hooks/useMatches.ts
export function useMatches(tournamentId: string, filters?: MatchFilters) {
  return useQuery({
    queryKey: ['matches', tournamentId, filters],
    queryFn: () => api.get(`/tournaments/${tournamentId}/matches`, { params: filters }),
    staleTime: 60_000, // 1 min
  });
}

// hooks/usePrediction.ts
export function useSavePrediction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ matchId, home, away }: SavePredictionArgs) =>
      api.put(`/predictions/${matchId}`, { predicted_home_score: home, predicted_away_score: away }),
    onSuccess: (_, { matchId }) => {
      queryClient.invalidateQueries({ queryKey: ['predictions'] });
      queryClient.invalidateQueries({ queryKey: ['match', matchId] });
    },
  });
}
```

---

## Styling Guidelines
- Dark theme primary: `bg-gray-900` body, `bg-gray-800` cards
- Accent: emerald green `#10b981` for CTAs and highlights
- World Cup feel: use team flag emojis or flag images from api-football `logo_url`
- Responsive: mobile-first, works well on 375px wide screens
- Bottom navigation bar on mobile: Home | Predictions | Leaderboard | Parties | Profile

---

## Environment Variables
```
VITE_API_BASE_URL=https://api.yourdomain.com    # or http://localhost:8000 in dev
VITE_COGNITO_USER_POOL_ID=us-east-1_XXXXXXXX
VITE_COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
VITE_ENVIRONMENT=dev
```

---

## Local Development
```bash
cd frontend
npm install
cp .env.example .env.local   # fill in local values
npm run dev                   # starts on http://localhost:5173
```

Backend must be running (see docker-compose.yml) for API calls to work.

---

## Build & Deploy
```bash
npm run build    # outputs to dist/
# CDK deploys dist/ to S3 and invalidates CloudFront
```
