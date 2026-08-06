# Atlas Docs frontend

Requires Node.js 20 or newer.

```sh
copy .env.example .env
npm install
npm run dev
```

Use `npm run build` for a production bundle and `npm run lint` for static analysis. During local
development, Vite proxies `/api` to FastAPI on port 8000. In production, serve `dist/` through a
CDN or reverse proxy and route `/api` to FastAPI on the same origin.

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the folder, component, state, API, routing, theme,
accessibility, and design rationale.
