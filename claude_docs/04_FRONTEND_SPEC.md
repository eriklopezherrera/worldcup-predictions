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
/leaderboard        → LeaderboardPage (Global + per-party tabs, podium + table)
/parties            → PartiesPage (my parties list)
/parties/create     → CreatePartyPage
/parties/join/:code → JoinPartyPage (shows party preview + join button)
/parties/:id        → PartyPage (members + party leaderboard)
/profile            → ProfilePage
/admin              → AdminPage (admins only — enter match results)
```

Protected routes: all except `/login`, `/register`, `/verify`, `/forgot-password`, `/parties/join/:code`.

`LoginPage` honours an optional `?redirect=<path>` query param and navigates there on success (only same-origin relative paths starting with `/` are accepted, to avoid open redirects). Defaults to `/tournaments`. This is how `/parties/join/:code` sends logged-out users to sign in and bounces them back to the invite.

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
| Rank | Player | Points | Exact Scores | Predictions |

Props:
```typescript
interface LeaderboardTableProps {
  entries: LeaderboardEntry[]
  currentUserId?: string   // row matching this id is highlighted emerald + "(you)"
  pageSize?: number        // rows revealed per "Load more" click, default 50
  isLoading?: boolean
}
```
- Avatar column with image (`avatar_url`) or initials fallback derived from `display_name`/`username`.
- Highlights the current user's row in emerald (`bg-emerald-500/10`).
- Rank delta badge driven by `LeaderboardEntry.rank_delta`: `> 0` → ▲n green, `< 0` → ▼n red, `0`/`null`/absent → — grey.
- Client-side pagination: shows `pageSize` rows, "Load more" reveals another page. Resets when `entries` change (tab/tournament switch).
- `Exact` and `Predictions` columns are hidden below the `sm` breakpoint (mobile shows rank, player, points).
- Reused by both `LeaderboardPage` (global + party tabs) and `PartyPage` (single party).

### `LeaderboardPage`
- Tabs: **🌍 Global** plus one tab per non-global party the user belongs to (`useParties`, filtered on `!is_global`).
- Tournament selector dropdown, shown only when more than one tournament exists; defaults to the active tournament.
- Top-3 **podium** above the table: 1st centered, larger, with crown + 🥇/🥈/🥉 medals; 2nd/3rd flank it. Falls back gracefully with fewer than 3 entries.
- Data source switches on the active tab: `useGlobalLeaderboard(tournamentId)` vs `usePartyLeaderboard(partyId, tournamentId)`.
- Replaces the earlier `GlobalLeaderboardPage` stub (deleted).

### `PartiesPage`
- Lists the user's parties (`useParties`). Each row shows party name, member count, and the user's rank within that party.
  - Per-row rank is resolved by querying that party's leaderboard for the party's tournament (or the active tournament if the party isn't tournament-scoped) and finding the current user's entry.
- "Create Party" button → `/parties/create`.
- "Join with code" input → `useJoinParty`, navigates to the party on success; shows the API `detail` on error.

### `CreatePartyPage`
- Form: party name (required, ≤80 chars) + optional tournament filter dropdown ("All tournaments" = no filter).
- On success (`useCreateParty`), swaps to a success panel showing the generated invite code and shareable link (`{origin}/parties/join/{invite_code}`), each with a copy button, plus a "Go to party" link.

### `JoinPartyPage` (public, `/parties/join/:code`)
- Public invite landing. Loads `usePartyPreview(code)` and shows party name + member count, and up to 3 leading members **if** the preview payload includes `top_members` (see `PartyPreview` below).
- "Join Party" button: if logged out, redirects to `/login?redirect=/parties/join/{code}`; if logged in, calls `useJoinParty` and navigates to the party.
- Handles invalid/unknown codes with an "Invite not found" state.

### `PartyPage`
- Header: party name, member count, copyable invite code, and a "Share invite link" button that copies `{origin}/parties/join/{invite_code}`.
- Party-scoped leaderboard via `LeaderboardTable` (uses the party's tournament, falling back to the active tournament).
- "Leave" button (`useLeaveParty`, with confirm) — hidden for the global party. Invite code / share / leave controls are all hidden when `is_global`.

### `ProfilePage`
- Shows display name, username, email (`useCurrentUser`).
- Inline edit of display name (`useUpdateUser` → `PATCH /users/me`); sending an empty value clears it (`null`).
- Stat cards: total points, exact scores, predictions made (`usePredictionSummary`), and **best rank** (derived from the active tournament's global leaderboard entry for the current user; shows "—" if unranked).
- Logout button (Zustand `authStore.logout`).

### `AdminPage` (`/admin`)
- Renders an "access denied" state unless `useCurrentUser().is_admin` (the backend
  enforces this too — the page check is UX only).
- Tournament selector + filter tabs: **To score** (kicked off, no final score) |
  **Finished** | **All**.
- Each match row has score inputs and a submit button → `useSetMatchResult`
  (`PUT /admin/matches/{id}/result`). Shows `predictions_scored` /
  `leaderboards_recomputed` from the response on success.
- Resubmitting corrects a previously entered score (backend re-scores idempotently).

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

Implemented hooks by file:
- `hooks/useTournaments.ts` — `useTournaments`, `useTournament(id)`
- `hooks/useMatches.ts` — `useMatches(tournamentId, filters?)`
- `hooks/usePredictions.ts` — `usePredictions(filters?)`, `usePredictionSummary`, `useSavePrediction` (optimistic)
- `hooks/useLeaderboard.ts` — `useGlobalLeaderboard(tournamentId, params?)`, `usePartyLeaderboard(partyId, tournamentId)`
- `hooks/useParties.ts` — `useParties`, `useParty(id)`, `usePartyMembers(id)`, `usePartyPreview(code)`, `useCreateParty`, `useJoinParty`, `useLeaveParty`
- `hooks/useUser.ts` — `useCurrentUser`, `useUpdateUser` (`PATCH /users/me`; omit a field to leave it unchanged, send `null` to clear)
- `hooks/useAdmin.ts` — `useSetMatchResult` (`PUT /admin/matches/{id}/result`; invalidates `matches`, `leaderboard`, `predictions` caches)

> ⚠️ **Known gap:** `useGlobalLeaderboard` calls `GET /tournaments/{id}/leaderboard`,
> which is not implemented in the backend — the Global tab on `LeaderboardPage` and
> the "best rank" stat on `ProfilePage` currently fail. See `02_BACKEND_API_SPEC.md`.

### Type notes (`src/types/index.ts`)
- `LeaderboardEntry.rank_delta?: number | null` — optional, drives the `LeaderboardTable` delta badge. Not yet populated by the backend leaderboard response; the UI treats absent/`0`/`null` as "no change" (—).
- `PartyPreview extends Party { top_members?: PartyMember[] }` — return type of `usePartyPreview`. The public `GET /parties/invite/{code}` endpoint currently returns party info only; `top_members` is rendered on `JoinPartyPage` when present and otherwise omitted.

---

## Styling Guidelines
- Dark theme primary: `bg-gray-900` body, `bg-gray-800` cards
- Accent: emerald green `#10b981` for CTAs and highlights
- World Cup feel: use team flag emojis (team `logo_url` is currently null — the WC2026 JSON has no logo data)
- Responsive: mobile-first, works well on 375px wide screens
- Bottom navigation bar on mobile: Home | Predictions | Leaderboard | Parties | Profile

---

## Environment Variables
```
VITE_API_BASE_URL=http://localhost:8000   # prod: the API Gateway URL
VITE_COGNITO_USER_POOL_ID=us-east-1_XXXXXXXX
VITE_COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
VITE_ENVIRONMENT=dev
```
All are baked in at build time. For deployed envs, `infrastructure/scripts/deploy.sh`
writes `frontend/.env.production` from the CDK stack outputs before the final build.

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
