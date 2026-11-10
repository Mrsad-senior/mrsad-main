# Deploying the gateway on AWS EC2

This runs the gateway on one Linux server with Docker Compose. Its database is the team's Supabase Postgres
(project `zrwffxwlyapqgporsobf`). A Cloudflare Tunnel publishes its API at `https://api.mirsad-app.com`,
which is the address the web UI on Cloudflare (`https://mirsad-main.badmick73.workers.dev`, see
`docs/web-ui.md`) calls.

The tunnel makes an outbound connection from the server to Cloudflare, so the server opens no web ports and
needs no certificate of its own. The server also needs no GitHub access: you copy the code from your own machine.

| File | Role |
|---|---|
| `docker-compose.yml` | gateway (`mirsad`) and a local PostgreSQL (`db`), shared with local Docker use |
| `deploy/ec2/compose.yml` | EC2 additions: the database comes from `MIRSAD_DATABASE_URL` and the local `db` service is never started; `cloudflared` runs the tunnel; the gateway port is bound to `127.0.0.1`; each service gets only the `.env` settings it needs (the tunnel token goes only to `cloudflared`) |
| `deploy/ec2/env.example` | template for the server's `.env` |

The server's `.env` sits in the repo root next to `docker-compose.yml`. Its `COMPOSE_FILE` line makes a
plain `docker compose ...` use both compose files. `deploy/ec2/compose.yml` uses `!override` and `!reset`,
which need Docker Compose 2.24.4 or later.

## Before you start

- **Security group (inbound):** only 22, from your own IP. Leave 80, 443 and 8700 closed. Outbound must
  allow the tunnel (TCP and UDP 7844 to Cloudflare) and Postgres (TCP 5432 to Supabase); the default
  "all outbound" rule does.
- **Your IP changes:** home connections often get a new public IP. If SSH suddenly times out, update the
  rule's source to your current IP.
- **Key on Windows:** OpenSSH refuses a key that other accounts can read:
  `icacls mirsad-key.pem /inheritance:r /grant:r "%USERNAME%:(R)"`.

The examples use `ubuntu@SERVER_IP`. On Amazon Linux the user is `ec2-user`.

## 1. Create the tunnel

In the Cloudflare dashboard, open Zero Trust → Networks → Tunnels and follow these steps:

1. Create a tunnel of type **Cloudflared**, named for example `mirsad-ec2`.
2. On the install page, pick Docker. Copy the long token after `--token` in the command shown; it is the
   `TUNNEL_TOKEN` for step 5. Don't run the command: compose starts `cloudflared` for you.
3. Add a public hostname:
   - subdomain `api`, domain `mirsad-app.com`
   - service type **HTTP**, URL **`mirsad:8700`**

   `cloudflared` runs inside the compose network, where the gateway is called `mirsad`, so `localhost`
   would not work here.
4. Cloudflare then creates the proxied `api` DNS record itself. If an `api` record already exists, delete it first.

## 2. The database

**How the tables get created.** On every start the gateway runs SQLAlchemy's `create_all`
(`src/mirsad/storage/database.py`). It creates whichever of its tables and indexes are missing, in the `public`
schema:

- `users`, `agents`, `policies`
- `audit_events`, `approvals`, `push_subscriptions`

An empty Supabase database is all it needs; there are no migrations to run. `create_all` never alters or drops
an existing table, which has two consequences:
- If a table with one of these names already exists in `public`, the gateway uses it as it is. Check that
  the names are free before the first start.
- A later gateway version that adds columns needs a manual `ALTER TABLE`.

**Connection string.** Use the **session pooler**. Supabase's direct host (`db.<project-ref>.supabase.co`)
has only an IPv6 address, and EC2 instances in a default VPC have no IPv6. Don't use the transaction pooler
(port 6543) either: psycopg prepares statements it runs repeatedly, and transaction mode doesn't support
prepared statements.

In the Supabase dashboard, click **Connect**, pick **Session pooler** and copy its URI. Then make three changes:

```text
postgresql://postgres.<project-ref>:[YOUR-PASSWORD]@<pooler host>:5432/postgres                         (copied)
postgresql+psycopg://postgres.<project-ref>:<password>@<pooler host>:5432/postgres?sslmode=require      (for .env)
```

1. Change the scheme to `postgresql+psycopg://`. The image has psycopg 3 only, and with plain `postgresql://`
   SQLAlchemy looks for psycopg2, so the gateway fails at start.
2. Replace `[YOUR-PASSWORD]` with the **database password** (Project Settings → Database). Don't use an API
   key. Percent-encode any of `@ : / ? # % [ ]` in it, e.g. `@` → `%40`.
3. Append `?sslmode=require`, so the connection is always encrypted.

In `.env`, wrap the whole URL in single quotes.

**Keep the tables away from the Data API.** Supabase serves tables in `public` through its Data API to anyone
holding the publishable key, and that key is in the public web bundle. Right after the first start, enable
Row Level Security on all six tables, with no policies:

```sql
alter table public.users              enable row level security;
alter table public.agents             enable row level security;
alter table public.policies           enable row level security;
alter table public.audit_events       enable row level security;
alter table public.approvals          enable row level security;
alter table public.push_subscriptions enable row level security;
```

The gateway connects as `postgres`, which owns these tables, so RLS doesn't restrict it. Then run Advisors →
Security Advisor in the dashboard. It reports "RLS enabled, no policy" for each table, which is the intended state.

## 3. Swap, Docker and Compose

A 1 GB instance needs swap, or the image build runs out of memory:

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Ubuntu (Docker's own apt repository):

```bash
sudo apt-get update && sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER"   # log out and back in to use docker without sudo
```

Amazon Linux 2023 packages Docker but not the Compose plugin, so download that from its GitHub releases:

```bash
sudo dnf install -y docker && sudo systemctl enable --now docker && sudo usermod -aG docker ec2-user
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
```

## 4. Copy the code

On your machine, from the repo root:

```bash
git -c core.autocrlf=false archive --format=tar.gz -o mirsad.tar.gz HEAD -- . ':!.env.example'
scp -i mirsad-key.pem mirsad.tar.gz ubuntu@SERVER_IP:
ssh -i mirsad-key.pem ubuntu@SERVER_IP 'mkdir -p ~/mirsad && tar -xzf mirsad.tar.gz -C ~/mirsad && rm mirsad.tar.gz'
```

`git archive` packs only committed files. So `.git`, `node_modules`, `.env` files, `web/.env.local`,
`.mcp.json` and `mobile/` (when it is not on the branch) never leave your machine. `core.autocrlf=false`
keeps Linux line endings when you pack on Windows. Commit `deploy/ec2/` first, or copy it separately.

## 5. The server's `.env`

```bash
cd ~/mirsad && cp deploy/ec2/env.example .env && chmod 600 .env
openssl rand -hex 32   # run once for each generated secret
nano .env
```

| Line | Needed | What |
|---|---|---|
| `MIRSAD_SECRET_KEY=` | yes | signs login tokens and the audit hash chain. Changing it later logs everyone out and makes `mirsad audit verify` fail on old events |
| `MIRSAD_ADMIN_PASSWORD=` | yes | password of the first admin (`MIRSAD_ADMIN_USERNAME`). Read only on a start that finds no users in the database |
| `TUNNEL_TOKEN=` | yes | the tunnel token from step 1 |
| `MIRSAD_DATABASE_URL=` | yes | the Supabase session pooler URL from step 2, in single quotes |
| `MIRSAD_LLM_BASE_URL=` / `MIRSAD_LLM_MODEL=` | yes | the demo agent's LLM, see Demo LLM below |
| `MIRSAD_LLM_API_KEY=` | for a hosted API | that LLM's key, typed at a hidden prompt (below) |
| `MIRSAD_VAPID_PUBLIC_KEY=` / `MIRSAD_VAPID_PRIVATE_KEY=` | no | web push for the approver PWA; set both or neither |

The gateway needs no Supabase API key (publishable or secret): it talks to Supabase only as a Postgres
database. Its only third-party key is the demo LLM's.

### Audit verification after a redeploy

Keep `MIRSAD_SECRET_KEY` unchanged while reusing the same database. If the Overview page reports that audit
verification failed, click **Verify now** and record the first bad event before changing anything. An HMAC
mismatch at event 1 commonly means the server is using a different signing key from the one that created the
stored chain. Restore the original key and recreate the `mirsad` service. Do not re-sign or delete the old
events: if the original key cannot be recovered, preserve/export the database as evidence and start a new,
explicitly documented audit chain.

### Demo LLM

The Demo Console's agent (`MIRSAD_ENABLE_DEMO=true`) gets its replies from an LLM. No Ollama runs on this
server, so point it at a hosted OpenAI-compatible API, such as Groq:

- `MIRSAD_LLM_BASE_URL`: the API's base URL, ending in `/v1`. The agent calls `<base URL>/chat/completions`.
  For Groq it is `https://api.groq.com/openai/v1`.
- `MIRSAD_LLM_MODEL`: a model that supports tool calls, for example Groq's `openai/gpt-oss-120b`.
- `MIRSAD_LLM_API_KEY`: the API's key, sent as `Authorization: Bearer <key>`. Leave it empty for an
  endpoint that needs none.

Compose refuses to start while the base URL or the model is empty, even with the demo off. The same key also
serves the gateway's `/v1` proxy to any agent holding a Mirsad agent key, so give it a spending limit.

The two optional security judges can use the same hosted endpoint. They resolve their connection in this order:

1. `MIRSAD_JUDGE_BASE_URL` / `MIRSAD_JUDGE_API_KEY` when set;
2. `MIRSAD_LLM_BASE_URL` / `MIRSAD_LLM_API_KEY`;
3. local Ollama at `http://127.0.0.1:11434/v1`, without an API key.

Set `MIRSAD_JUDGE_ENABLED=1` for tool-result injection classification and
`MIRSAD_INTENT_JUDGE_ENABLED=1` for original-request intent checks. The configured judge model must exist at
the selected endpoint. Both judges fail closed if an enabled provider fails or times out.

Don't type the key in `nano`, where it shows on screen. `read -s` reads it without echoing it and keeps it
out of the shell history:

```bash
cd ~/mirsad
read -rsp 'LLM API key: ' K && echo
(umask 077 && K="$K" awk '/^MIRSAD_LLM_API_KEY=/ { $0 = "MIRSAD_LLM_API_KEY=" ENVIRON["K"] } 1' .env > .env.new) \
  && mv .env.new .env; unset K
grep -c '^MIRSAD_LLM_API_KEY=.' .env   # prints 1 once the key is set, without showing it
```

When you change the key on a running server, run `docker compose up -d` afterwards to recreate the gateway.

## 6. Build and start

```bash
cd ~/mirsad
docker compose build                 # gateway image with the dashboard and approver PWA built in
docker compose up -d                 # starts mirsad and cloudflared; db stays off
docker compose ps                    # mirsad should become "healthy"
docker compose logs -f cloudflared   # wait for "Registered tunnel connection"
```

Then enable RLS as in step 2, and check from any machine:

```bash
curl -fsS https://api.mirsad-app.com/healthz
curl -sI -H 'Origin: https://mirsad-main.badmick73.workers.dev' https://api.mirsad-app.com/healthz | grep -i access-control-allow-origin
```

`/healthz` doesn't touch the database. The gateway creates its tables when it starts, though, so a
"healthy" container means it reached Supabase.

Then sign in on `https://mirsad-main.badmick73.workers.dev` as the admin. The gateway's own dashboard
is also served at `https://api.mirsad-app.com/`.

## Updating

Repeat step 4, then `docker compose up -d --build`. The data lives in Supabase and is untouched by rebuilds.
Supabase's own backups cover it. For a copy of your own, run `pg_dump` with the same URL, but with
`postgresql://` as the scheme: `+psycopg` is SQLAlchemy-only.

## Things to know

- **Client IP.** The gateway sees every request as coming from `cloudflared`, because uvicorn runs with
  `proxy_headers=False`. As a result:
  - The login throttle's per-IP limit (30 failures in 5 minutes) is shared by all users, so a burst of bad
    logins from anywhere locks everyone out for up to 5 minutes.
  - `auth.login_failed` audit events record the tunnel's address instead of the user's.
- **Latency.** Every tool call writes to the database, so the Supabase region matters; the pooler host
  names it. A project far from the server's region adds that round trip to every request.
- **Live stream.** Cloudflare closes a proxied connection after 100 seconds without data. The `/api/stream`
  feed sends a heartbeat every 15 seconds, so it stays open.
- **Port 8700** is bound to `127.0.0.1` only. To reach it directly, open a tunnel with
  `ssh -i mirsad-key.pem -L 8700:127.0.0.1:8700 ubuntu@SERVER_IP` and use `http://127.0.0.1:8700`.
- **Allowed origins.** `MIRSAD_CORS_ORIGINS` must list every web origin that calls the API, exactly
  (scheme, host, no trailing slash). After editing `.env`, run `docker compose up -d`; it recreates only the
  changed containers.
- **More settings.** The gateway receives only the `MIRSAD_` settings listed under `mirsad.environment` in
  `deploy/ec2/compose.yml`. To use another one from `src/mirsad/config.py`, add it there as well as to `.env`.
