# Quick Start

> A contributor-facing read. The full instructions live in the repo
> [README · Quick start](https://gitee.com/perry-space/study-club#快速开始本地测试) (Gitee).

Start the full local stack (content + backend + frontend) with four commands:

```bash
cp .env.example .env          # generate env vars (ports & feature flags)
scripts/dev/bootstrap.sh      # optional one-step setup
scripts/dev/up-all.sh         # start db → api → web (each orchestrated independently)
scripts/seed/seed.sh          # import content & seed data
```

> The four services are **orchestrated independently** (`deploy/mongo`, `deploy/api`,
> `deploy/web`, `deploy/admin`), all with `network_mode: host` — containers bind host ports
> directly, so there is **no port mapping**. `up-all.sh` just calls them in dependency order.

## Prerequisites

| Dependency | Version |
| --- | --- |
| Node.js | ≥ 20 |
| pnpm | 9.12.0 |
| Python | 3.12 |
| Docker | Docker + Docker Compose |

## URLs

| Purpose | URL | Port source |
| --- | --- | --- |
| **Student / parent app** | `http://localhost:8080/` | `WEB_PORT` |
| Admin console (internal) | `http://localhost:8081/` | `ADMIN_PORT` |
| API | `http://localhost:8000/api/v1` | `API_PORT` |
| API docs (Swagger) | `http://localhost:8000/docs` | `API_PORT` |
| Health check | `http://localhost:8000/api/v1/health` | `API_PORT` |
| MongoDB | `mongodb://localhost:27017/study_club` | `MONGO_PORT` |

## Admin console (optional internal tool)

The admin console is **not part of the default `up-all.sh` chain**. Set an admin password first:

```bash
scripts/api/hash-password.sh  # generate an Argon2id password hash → put it in .env
scripts/api/restart.sh        # let the api read the new hash
scripts/admin/up.sh           # → http://localhost:8081/
```

> ⚠️ Keep the single quotes around the hash line: Argon2 hashes contain many `$`, and Docker
> Compose's dotenv parsing would otherwise treat them as variable references and blank them out.
>
> ⚠️ The admin console is a **single-user internal tool** — do not expose it publicly.

## Useful scripts

```
scripts/
├── db/     # start stop reset backup restore shell logs init-indexes
├── api/    # build up down logs restart hash-password gen-invite-keys issue-invites
├── web/    # dev build up down logs
├── admin/  # dev build up down logs
├── seed/   # seed.sh + data/*.json
├── content/# content build, schema validation, manifest generation
└── dev/    # up-all / down-all / status / bootstrap
```

- Stop everything: `scripts/dev/down-all.sh`
- Status: `scripts/dev/status.sh`
- Frontend dev server only: `scripts/web/dev.sh` → `http://<LAN IP>:5173/`

> Testing from a phone / iPad on the same Wi-Fi: open `http://<host-LAN-IP>:8080/`.

## Next steps

- How the system is built → [Architecture Overview](./architecture.md)
- Full design docs → repo [`docs/`](https://gitee.com/perry-space/study-club/tree/master/docs)
