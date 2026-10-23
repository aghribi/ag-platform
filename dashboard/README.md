# ag-dashboard

Next.js dashboard for the ag-tools API.

```sh
npm ci
NEXT_PUBLIC_API_URL=http://localhost:8100 npm run dev
```

Deploy to Cloudflare Workers (custom domain in `wrangler.jsonc`):

```sh
npm run deploy
```

Build-time settings, all optional (defaults in `lib/config.ts`):

| Variable | Default |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://ai-api.artifact-network.org` |
| `NEXT_PUBLIC_APP_URL` | `https://ai.artifact-network.org` |
| `NEXT_PUBLIC_CONTACT_EMAIL` | `ai@artifact-network.org` |
| `NEXT_PUBLIC_STATUS_URL` | `https://status.artifact-network.org` |
