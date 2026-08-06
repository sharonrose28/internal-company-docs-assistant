# Frontend architecture

## Folder structure

`app/` owns composition, providers, and routing. `features/` owns vertical product capabilities.
`components/ui/` contains accessible Shadcn-style primitives; `components/layout/` composes product
chrome. `api/` is the only HTTP boundary. `stores/` contains small client-state stores. `lib/` and
`styles/` contain framework-independent helpers and design tokens.

## Component hierarchy

```text
AppProviders
├── ErrorBoundary
├── QueryClientProvider
├── BrowserRouter
│   └── AppRouter
│       ├── LoginPage
│       └── ProtectedRoute
│           └── AppShell
│               ├── Sidebar / mobile drawer
│               ├── ThemeToggle
│               └── ChatPage | DocumentsPage
└── ToastRegion
```

The shell persists across feature navigation, while feature routes are lazy-loaded. Primitives own
focus behavior and visual variants so features remain product-focused and consistent.

## State management

TanStack Query is the source of truth for documents, conversations, and all other server state. It
handles deduplication, staleness, retries, and mutation invalidation. Zustand is limited to state
that has no server owner: the access token, theme preference, and transient toasts. Component-local
state holds input and disclosure state. This avoids duplicating backend data in a global store.

The JWT uses `sessionStorage`, not `localStorage`, reducing persistence after a browser session.
For the strongest production posture, the backend should move authentication to a Secure,
HttpOnly, SameSite cookie with CSRF protection; JavaScript cannot fully protect bearer tokens from
XSS.

## API architecture

`client.ts` configures one Axios instance, attaches authorization, normalizes errors, applies a
finite timeout, and clears invalid sessions on 401. `endpoints.ts` exposes domain-oriented typed
functions. Features never construct URLs. `query-keys.ts` centralizes cache identity and prevents
invalidation drift. The frontend expects `/api` at runtime, allowing the reverse proxy to keep API
and UI same-origin; `VITE_API_URL` supports other environments.

## Routing

Public `/login` is separated from the protected shell. `/chat` and `/documents` require an active
session and unknown URLs render a real 404. The attempted location is retained through login.
Routes are feature-level code-split boundaries, reducing initial login payload without creating
tiny network chunks for individual controls.

## Theme and visual system

Semantic CSS variables define background, surface, border, text, muted text, and brand colors.
Tailwind consumes those variables, so components express intent rather than hard-coded light/dark
colors. Light, dark, and operating-system modes are supported, persisted locally, and set
`color-scheme` for native controls. The restrained violet accent, neutral surfaces, fine borders,
and compact typography produce a Linear/Notion-like enterprise hierarchy.

## Accessibility and resilience

All controls have accessible names, forms connect labels and errors, navigation uses semantic
landmarks, status messages use appropriate live regions, and layouts remain functional from 320px.
Focus is visible, color is never the only status signal, reduced-motion preferences collapse
animation, loading screens expose status semantics, and the error boundary offers recovery.

## Design decisions

- Shadcn-style owned components avoid a theme-runtime dependency and make audits straightforward.
- React Hook Form plus Zod provides a single runtime and compile-time validation contract.
- Framer Motion is reserved for orientation-preserving transitions, not decorative movement.
- React Markdown renders answer structure while raw HTML remains disabled by default.
- Source cards stay separate from answer prose so provenance remains inspectable and structured.
- Mobile navigation becomes a modal drawer; desktop navigation collapses to maximize reading width.
- Destructive actions require confirmation and server mutations invalidate only affected queries.
