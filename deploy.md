# Deploying Provenyx for free

This guide puts the whole project online at **no cost**:

| Part | Host | Free tier used |
|---|---|---|
| Web dashboard (`frontend/`) | **Vercel** | Hobby plan |
| API (`backend/`) | **Render** | Free web service |
| Database | **Neon** | Free Postgres (0.5 GB) |
| GitHub sign-in | **GitHub OAuth App** | Free |
| Keep-alive pings | **cron-job.org** or **UptimeRobot** | Free |
| PR trust gate | **GitHub Actions** | Free for public repositories |
| VS Code extension | **VS Code Marketplace** (optional) | Free |

No credit card is needed for any of these at the time of writing, but free tiers change. Check each provider's current limits before relying on them.

```
Browser ──► Vercel (Next.js dashboard) ──/api/* proxy──► Render (FastAPI) ──► Neon (Postgres)
                                                              │
VS Code extension ────────────────────────────────────────────┘   + npm registry, OSV (public APIs)
```

### Why the dashboard proxies the API

The dashboard and the API live on different sites (`*.vercel.app` and `*.onrender.com`). To a browser, the API's GitHub session cookie would then be a **third-party cookie**, which Safari and Chrome block. GitHub sign-in would silently fail.

So Vercel proxies `/api/*` to Render (see `frontend/next.config.mjs`), and the browser only ever talks to the Vercel site. Cookies stay first-party, and CORS is not involved.

---

## Before you start

- Push the repository to GitHub. Vercel and Render deploy straight from it.
- Choose your Vercel project name now, because several settings need its URL. The examples below use `provenyx`, which gives `https://provenyx.vercel.app`. Replace it everywhere with yours.
- Generate two random secrets. Run this twice:

  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

  The first is the **API access key**. The second is the **GitHub session secret**. Alternatively, let Render generate both (step 2 does this) and copy them from its dashboard.

---

## 1. Database: Neon (free Postgres)

Render's free web services have no persistent disk. With the default SQLite database, every scan would disappear on each restart, redeploy or sleep.

1. Sign up at <https://neon.tech> and create a project (any region; pick one close to your Render region).
2. On the project dashboard, copy the **connection string**. It looks like
   `postgresql://user:password@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require`.
3. Keep it for step 2. Provenyx creates its tables automatically on first start, and accepts the URL as Neon gives it (it switches to the `psycopg` driver itself).

> **Skipping this:** leave `PROVENYX_DATABASE_URL` unset and the API uses SQLite. Everything works, but scan history is lost whenever the service restarts. That's fine for a quick demo.

---

## 2. API: Render (free web service)

The repository includes a Render Blueprint (`render.yaml`) with the build command, start command, health check and environment variables already set.

1. Sign up at <https://render.com> with your GitHub account.
2. Click **New → Blueprint**, select this repository, and confirm. Render reads `render.yaml` and creates the `provenyx-api` service on the **Free** plan.
3. Fill in the variables Render asks for:

   | Variable | Value |
   |---|---|
   | `PROVENYX_DATABASE_URL` | Neon connection string from step 1 (or leave empty for SQLite) |
   | `PROVENYX_FRONTEND_URL` | `https://provenyx.vercel.app` |
   | `PROVENYX_CORS_ORIGINS` | `https://provenyx.vercel.app` |
   | `PROVENYX_GITHUB_CALLBACK_URL` | `https://provenyx.vercel.app/api/github/auth/callback` |
   | `PROVENYX_GITHUB_CLIENT_ID` | leave empty for now (step 4) |
   | `PROVENYX_GITHUB_CLIENT_SECRET` | leave empty for now (step 4) |

   `PROVENYX_API_KEY` and `PROVENYX_GITHUB_SESSION_SECRET` are generated automatically. `PROVENYX_SECURE_COOKIES=true` is preset.
4. Deploy. When it's live, open `https://provenyx-api.onrender.com/health` (your service URL may differ). You should see
   `{"status":"ok","service":"provenyx-api","version":"0.1.0"}`.
5. In the service's **Environment** tab, copy the generated `PROVENYX_API_KEY` value for step 3.

<details><summary>Manual setup instead of the Blueprint</summary>

**New → Web Service**, connect the repository, and set:

- **Root Directory:** `backend`
- **Runtime:** Python
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips '*'`
- **Health Check Path:** `/health`
- **Instance Type:** Free
- **Environment:** `PYTHON_VERSION=3.12.8`, plus every variable in the table above, plus `PROVENYX_API_KEY`, `PROVENYX_GITHUB_SESSION_SECRET` (your two secrets) and `PROVENYX_SECURE_COOKIES=true`.

</details>

**About the free plan:** the service **sleeps after 15 minutes without traffic**, and the next request waits about a minute while it wakes. Step 5 keeps it awake. Free services get 750 instance hours a month, which is enough for one service running all month.

---

## 3. Dashboard: Vercel (Hobby)

1. Sign up at <https://vercel.com> with your GitHub account.
2. Click **Add New → Project** and import this repository.
3. Set **Root Directory** to `frontend`. Vercel detects Next.js; keep the default build settings.
4. Add the **Environment Variables** (for all environments):

   | Variable | Value | Purpose |
   |---|---|---|
   | `PROVENYX_API_PROXY_URL` | `https://provenyx-api.onrender.com` | Where Vercel proxies `/api/*` (server side only) |
   | `NEXT_PUBLIC_PROVENYX_API_URL` | `/` | Makes the browser call the Vercel site itself |
   | `NEXT_PUBLIC_PROVENYX_API_KEY` | the `PROVENYX_API_KEY` from Render | Sent as `X-Provenyx-Key` |

5. Name the project to match the URL you chose (e.g. `provenyx`) and click **Deploy**.
6. Open `https://provenyx.vercel.app`. The landing page loads. Then check `https://provenyx.vercel.app/health`: it should return the same JSON as Render, which proves the proxy works.

These variables are read at **build time**. After changing any of them, redeploy (**Deployments → ⋯ → Redeploy**).

---

## 4. GitHub sign-in: OAuth App

1. Go to GitHub **Settings → Developer settings → OAuth Apps → New OAuth App**
   (<https://github.com/settings/applications/new>).
2. Fill in:

   | Field | Value |
   |---|---|
   | Application name | `Provenyx` |
   | Homepage URL | `https://provenyx.vercel.app` |
   | Authorization callback URL | `https://provenyx.vercel.app/api/github/auth/callback` |

   The callback goes through the **Vercel** URL, not Render's: that's how the session cookie stays first-party.
3. Click **Register application**, then **Generate a new client secret**.
4. In Render, set `PROVENYX_GITHUB_CLIENT_ID` and `PROVENYX_GITHUB_CLIENT_SECRET`, then save. Render redeploys.
5. On the landing page, click **Sign in with GitHub**. GitHub asks you to authorize the app, then sends you to the dashboard with your avatar in the navbar and sidebar.

**Every dashboard page requires sign-in.** Visitors who aren't signed in are sent to `/signin` and returned to the page they wanted afterwards. **Log out** is at the bottom of the sidebar. Until the OAuth App is configured, the sign-in page explains what's missing, so the dashboard stays locked.

The OAuth App asks for the `repo` and `read:user` scopes, because **GitHub projects** reads lockfiles from private repositories. Provenyx only makes read requests, and only for the lockfile you choose. The token is kept in an encrypted, HTTP-only cookie for 8 hours and is never stored in the database.

> **Local development** needs its own OAuth App, with callback `http://localhost:8000/api/github/auth/callback` and the client ID, secret and session secret in `backend/.env`. An OAuth App has exactly one callback URL.
>
> To work on the dashboard locally without any OAuth App, set `NEXT_PUBLIC_PROVENYX_REQUIRE_SIGN_IN=false` in `frontend/.env.local` and restart `npm run dev`. Never set it on Vercel.

---

## 5. Keep the API awake (free)

Use either service to request `https://provenyx-api.onrender.com/health` every **10 minutes**:

- **cron-job.org:** create a free account, then **Create cronjob** with that URL, set to every 10 minutes.
- **UptimeRobot:** add an **HTTP(s)** monitor with a 5-minute interval. You also get downtime emails.

`/health` needs no access key and does almost no work.

---

## 6. VS Code extension (optional)

Point the extension at the deployed API in VS Code settings:

```jsonc
{
  "provenyx.apiBaseUrl": "https://provenyx-api.onrender.com",
  "provenyx.dashboardUrl": "https://provenyx.vercel.app",
  "provenyx.apiKey": "<PROVENYX_API_KEY from Render>"
}
```

To publish it for others: create a free publisher at <https://marketplace.visualstudio.com/manage> (the project uses publisher ID `Provenyx`). Then run `npm --prefix extension run vsix` and upload the `.vsix`, or use `npx @vscode/vsce publish`.

---

## 7. Pull request trust gate (already free)

`.github/workflows/dependency-trust-gate.yml` runs on every pull request that changes a `package-lock.json`. It needs nothing deployed: the gate runs inside the GitHub Actions runner, against the public npm and OSV APIs. GitHub Actions is free for public repositories (private repositories get a free monthly allowance).

Other repositories can use it too:

```yaml
- uses: actions/checkout@v4
- uses: <your-github-user>/DevKnights@main
  with:
    lockfile: package-lock.json
```

---

## 8. Check the deployment

- [ ] `https://provenyx-api.onrender.com/health` returns `"status":"ok"`.
- [ ] `https://provenyx.vercel.app/health` returns the same (the proxy works).
- [ ] `https://provenyx-api.onrender.com/api/scans` **without** the key returns `401`. The access key is enforced.
- [ ] The dashboard shows **Backend connected**.
- [ ] **Sign in** on the landing page returns you to the dashboard, with your avatar in the navbar.
- [ ] **GitHub projects** lists your repositories, and scanning one completes.
- [ ] **New scan** with `demo/fixtures/baseline-package-lock.json`, then `suspicious-update-package-lock.json`, produces findings.
- [ ] Redeploy the Render service, and the scans are still listed (Neon is persisting them).

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Dashboard says it **cannot reach the API** | `PROVENYX_API_PROXY_URL` is missing or wrong, or Vercel wasn't redeployed after setting it. Check `https://provenyx.vercel.app/health`. |
| First request takes ~1 minute | The free Render service was asleep. Set up step 5. |
| `401: A valid X-Provenyx-Key header is required` | `NEXT_PUBLIC_PROVENYX_API_KEY` (Vercel) or `provenyx.apiKey` (VS Code) differs from Render's `PROVENYX_API_KEY`. Redeploy Vercel after fixing it. |
| Sign-in returns `github_error=invalid_oauth_state` | The sign-in started on a different site from the one the callback returns to. Use the Vercel URL everywhere: `PROVENYX_FRONTEND_URL`, `PROVENYX_GITHUB_CALLBACK_URL` and the OAuth App's callback URL. |
| GitHub says **redirect_uri is not associated** | The OAuth App's callback URL doesn't exactly match `PROVENYX_GITHUB_CALLBACK_URL`. |
| Sign-in page says **GitHub sign-in isn't set up** | `PROVENYX_GITHUB_CLIENT_ID`, `_SECRET` or `_SESSION_SECRET` is missing on Render. |
| Scans disappear after a while | `PROVENYX_DATABASE_URL` isn't set, so the API is using SQLite on Render's temporary disk. |
| `429 Too many submissions` | The per-client rate limit (30 scans a minute). Raise it with `PROVENYX_SUBMISSION_RATE_LIMIT_PER_MINUTE`. |

Server logs, including the full error for any failed scan, are under **Logs** in the Render service.

---

## Security notes

- **The access key is shared, not per-user.** It keeps strangers and bots off an exposed API, but the dashboard's copy is visible in its JavaScript bundle. Scans are not yet owned by users: anyone who can use the dashboard can see every scan. Treat a deployment as a **team or demo workspace**, and don't scan lockfiles you couldn't share with everyone who has the link.
- Keep `PROVENYX_GITHUB_CLIENT_SECRET`, `PROVENYX_GITHUB_SESSION_SECRET` and `PROVENYX_API_KEY` out of the repository. Set them only in the Render and Vercel dashboards. Rotating the session secret signs everyone out.
- No package code is ever downloaded or executed, in production or in the trust gate.

---

## Suggestions

Free, optional improvements, roughly by value:

1. **Turn on AI ranking with Gemini's free tier.** Create a key at <https://aistudio.google.com/apikey>, then set `PROVENYX_AI_RANKING_ENABLED=true` and `PROVENYX_GEMINI_API_KEY` on Render. Only finding summaries are sent, never lockfiles. Check the dashboard shows Gemini rankings before you claim AI ranking in a demo.
2. **Use the trust gate as a required check.** Under the repository's **Settings → Branches**, add a branch protection rule for `main` that requires the *Dependency Trust Gate* checks. Risky dependency updates then can't be merged unreviewed.
3. **A custom domain.** Vercel connects your own domain for free, with HTTPS. Then update the three URL settings and the OAuth App.
4. **Release anchors on a public testnet.** The blockchain registry is local-only (Hardhat), so on this deployment, release verification honestly reports `unavailable`. To make it live for free, add a Sepolia network to `contracts/hardhat.config.ts` using a free RPC endpoint (e.g. Alchemy or Infura free tier) and faucet ETH, deploy the contract, then set `PROVENYX_REGISTRY_RPC_URL` and `PROVENYX_REGISTRY_ADDRESS` on Render. Keep the deployer key out of the repo.
5. **Monitoring.** UptimeRobot's free monitor (step 5) already emails you when the API goes down. Render's free plan keeps recent logs.

### What the free tiers don't give you

- **Cold starts**, if you skip the keep-alive.
- **One API instance.** The rate limiter and the startup recovery of interrupted scans assume a single instance, which is what the free plan runs.
- **Neon's free 0.5 GB.** Each scan stores its lockfile and graph, so a large monorepo lockfile takes a few MB. There is no scan deletion in the app yet; clear the `scans` and `scan_findings` tables in Neon's SQL editor if you approach the limit.
