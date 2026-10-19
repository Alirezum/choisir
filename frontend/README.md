# choosier frontend

Vue 3 + Vite single-page app for the choosier web UI. The API it talks
to lives in `../choosier/web.py`.

## Development

Terminal 1 — API server:

```sh
uv run choosier --web --port 8765
```

Terminal 2 — Vite dev server with hot reload (proxies `/api` to 8765):

```sh
npm install
npm run dev
```

## Production build

```sh
npm run build
```

Output lands in `../choosier/web_static/`, which `choosier --web`
serves from the same origin.
