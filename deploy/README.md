# Deploying Gold Market Intelligence (Phase 3)

This is an honest deployment guide. It tells you how to run the stack in a
way that is:

- non-root in-container
- TLS-terminated at the edge
- auth-gated with rotatable multi-user tokens
- capable of real-broker live trading **only after** the supervised dry-run
  checklist at the end of this file is completed

It does NOT claim the stack is battle-tested for real money. The OANDA
adapters are implemented and mock-tested but have not been validated
against the live OANDA service in this build.

---

## 1. Components

| Component   | What it does                                 | Where it runs          |
|-------------|----------------------------------------------|------------------------|
| `Dockerfile`| Packages the stdlib Python backend           | container              |
| `nginx`     | Terminates TLS, serves SPA, proxies `/api/*` | host (or sidecar)      |
| `certbot`   | Gets + renews Let's Encrypt certificates     | host (cron / systemd)  |
| Frontend    | Static SPA built by `npm run build`          | nginx `/var/www/...`   |

Architecture (production posture):

```
Browser  ──HTTPS──▶  nginx (TLS, static SPA)  ──HTTP(127.0.0.1)──▶  Docker: backend
                                                                    │
                                                                    ├──▶ OANDA REST v20
                                                                    ├──▶ FRED API
                                                                    └──▶ Anthropic API
```

The backend is NEVER exposed directly to the public internet.

---

## 2. Prerequisites

- Ubuntu 22.04 / Debian 12 (or anything that runs Docker + nginx)
- A domain pointed at the host (A / AAAA records)
- Docker 24+
- nginx 1.22+
- certbot (`apt install certbot python3-certbot-nginx`)

---

## 3. Tokens — multi-user auth

Create `/etc/gold-agent/tokens.json` (mode 0600, owned by root):

```json
[
  {"token": "alice-XXXXXXXXXXXXXXXXXXXXXXX", "principal": "alice", "scopes": ["read", "write"]},
  {"token": "ops-YYYYYYYYYYYYYYYYYYYYYYYYY", "principal": "ops",   "scopes": ["read"]},
  {"token": "admin-ZZZZZZZZZZZZZZZZZZZZZZ", "principal": "admin", "scopes": ["read", "write", "admin"]}
]
```

Rules:

- Tokens must be at least 16 characters. Use `openssl rand -hex 24` to generate.
- Each entry must have a unique `token` and `principal`.
- The file is re-read on every auth check (mtime-cached) — no restart to rotate.
- If the file is malformed, **all** requests are denied (fail-closed).

Mount into the container read-only at `/app/tokens/tokens.json`:

```bash
docker run -d --name gold-agent --restart=unless-stopped \
  -p 127.0.0.1:8888:8888 \
  -e API_TOKENS_FILE=/app/tokens/tokens.json \
  -e CORS_ALLOWED_ORIGINS=https://your-domain.example \
  -e DATA_PROVIDER=oanda \
  -e OANDA_API_KEY=... \
  -e OANDA_ACCOUNT_ID=... \
  -e OANDA_ENVIRONMENT=practice \
  -v /var/lib/gold-agent:/app/data \
  -v /etc/gold-agent:/app/tokens:ro \
  gold-agent:latest
```

---

## 4. TLS — certbot + nginx

```bash
# 1. Copy the example into nginx sites-available.
sudo cp deploy/nginx.conf.example /etc/nginx/sites-available/gold-agent.conf
sudo sed -i 's/<your-domain>/your-domain.example/g' /etc/nginx/sites-available/gold-agent.conf
sudo ln -s /etc/nginx/sites-available/gold-agent.conf /etc/nginx/sites-enabled/

# 2. Obtain the initial cert. certbot will edit nginx to add the cert paths.
sudo certbot --nginx -d your-domain.example

# 3. Confirm auto-renewal.
sudo systemctl list-timers | grep certbot
```

Rotate nginx (reload, not restart, to avoid dropping in-flight connections):

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## 5. Going live — supervised dry-run checklist

The OANDA broker adapter (`backend/execution/oanda_broker.py`) is
**implemented but unvalidated** in this build. Before moving any real
money through it, complete every item below. Do not skip.

### Phase A — practice account, 1 week

- [ ] `OANDA_ENVIRONMENT=practice`, real practice credentials
- [ ] `LIVE_BROKER_ENABLED=true`, `system_mode=live` in settings
- [ ] Verify `GET /api/readiness` returns `ready: true` with no blockers
- [ ] Place ONE supervised practice-account order through a short Python harness using `backend.execution.oanda_broker.OandaLiveBroker`
- [ ] Reconcile against OANDA web UI:
  - [ ] Instrument matches (XAU_USD)
  - [ ] Units match (lots × 100, long → positive, short → negative)
  - [ ] Stop + target prices appear correctly in OANDA
  - [ ] `orderFillTransaction` returned matches OANDA's trade ID
- [ ] Close the same supervised practice trade through the broker harness and reconcile PnL
- [ ] Run autonomously for 5 trading days, spot-check fills daily
- [ ] Verify the broker-reported account summary matches the OANDA weekly balance

Current note: the default HTTP surface in this build exposes paper-trading routes only. The live broker is implemented at the Python adapter layer, so supervised practice validation should call `OandaLiveBroker` directly from a controlled script or REPL session rather than assuming public `/api/live/*` routes exist.

### Phase B — practice account, full week under load

- [ ] Enable scheduled analysis (or manual, several per day)
- [ ] Observe: any Claude-generated decisions are blocked unless all
      deterministic readiness checks pass. Sample 10 blocked decisions
      and confirm the block reason is visible in logs.
- [ ] Kill the container mid-trade. Verify: positions remain at OANDA,
      restart recovers correct state, no duplicate orders.
- [ ] Rotate API tokens mid-session; verify no auth errors.

### Phase C — live account, gated rollout

- [ ] `OANDA_ENVIRONMENT=live` **only after** Phase A + B pass cleanly
- [ ] Lower `max_position_lots`, `max_daily_loss` settings for first week
- [ ] Manual approval for first ~20 trades (use safe_mode toggle between)
- [ ] Daily reconciliation against OANDA statements
- [ ] **Final step, only after every box above is checked:** set
      `LIVE_CUTOVER_ACKNOWLEDGED=true` and restart the backend. Until this
      env var is `true`, every live-environment order is blocked by the
      readiness gate with `cutover_not_acknowledged`. This is intentional:
      the adapter is implemented but UNVALIDATED against the real live
      service in this build — the operator's explicit assertion that the
      supervised practice validation above is complete is the only way the
      gate opens. Revoke by unsetting the var or setting it to anything
      other than `true`.

If any of these steps reveals a discrepancy: revert, file an issue, do
not proceed.

---

## 6. What to watch in production

- `/api/health` — all of `connected`, `auth_enabled`, `data_provider_ready`
  should be true; `data_last_quote_age_seconds` should stay under 60 under
  active load.
- `/api/readiness` — `ready: true` before any live attempt; inspect blockers
  otherwise.
- `/api/auth/audit` — recent auth allow/deny events (last 50 by default).
- Container logs — every Claude call, every risk block, every readiness
  decision is logged with `data_provenance` for after-the-fact review.

---

## 7. What this deployment guide does NOT give you

- A 24/7 monitoring / alerting stack (Prometheus, Grafana, etc.) — run
  your own.
- Automatic failover between exchanges — one broker at a time by design.
- Regulatory compliance for your jurisdiction — that is your problem.
- A guarantee the strategy is profitable — it is a decision-support
  framework, not a magic money machine.
