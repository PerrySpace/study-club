# Architecture Overview

> Contributor-facing read. Full design:
> [02-1 System architecture & tech choices](https://gitee.com/perry-space/study-club/blob/master/docs/02-系统架构/01-系统总体架构与技术选型.md) (Gitee).

Given the constraints (no capabilities requiring a corporate entity, free for everyone, open
source, self-hostable), the system uses a **server-authoritative + content-as-repo +
single-machine self-hosted backend** architecture.

## Layers

```
User device (browser / PWA)
  apps/web   Vue3 + Vite + Pinia   (phone · iPad · desktop, three responsive tiers)
  packages/core  ⭐ zero-platform, subject-agnostic (algorithms · stores · types · contracts · flags)
        │  HTTPS  /api/v1/*  (same-origin proxy)
        ▼
✅ Cloud backend (self-hosted, single machine): FastAPI + MongoDB 7 + single-admin console

⛔ Hidden layer (needs a corporate entity): phone/WeChat accounts · payments · push ·
   mini-program · iOS/Android app — off by default, not bundled, not deployed
```

## Design principles

| Principle | Practice |
| --- | --- |
| **Server-authoritative** | Data, profiles, progress and content use the server as the single source of truth |
| **Content/code separation** | Content lives in `content/` as JSON; contributors need no frontend knowledge |
| **Content-as-repo** | Git handles versioning, review, rollback and audit |
| **Repository abstraction** | Data access always goes through `packages/core` |
| **Flags off by default** | Entity-dependent capabilities exist but are unreachable and unbundled |
| **Single-machine maintainable** | No Redis, no message queue, no K8s, no microservices |
| **Contract-first** | Unified prefix `/api/v1`; envelope `{code, message, data\|errors, request_id}` |

## Cross-platform reuse boundary

| Layer | Reuse |
| --- | --- |
| Algorithms, state, types, contracts, flags | ✅ 100% reused (`packages/core`, zero DOM / platform API) |
| Platform capabilities (recording, storage, notifications) | ❌ Implemented per shell via dependency injection |
| View layer (pages, components) | ❌ Rewritten per shell |

> ⚠️ Core discipline: once `window`, `document` or `uni.xxx` appears in `packages/core`, the
> reuse rate drops from 95% to 0.

## Tech choices

| Layer | Choice |
| --- | --- |
| Frontend | Vue 3 + TypeScript + Vite + Pinia + vue-router + vite-plugin-pwa |
| Backend | Python 3.12 + FastAPI + Uvicorn + Pydantic v2 |
| Database | MongoDB 7 (motor async) — server single source of truth |
| Cache | ❌ No Redis (JWT + `devices` revocation; content is small and fully loaded) |
| Deploy | Docker Compose per-service + `network_mode: host` + nginx same-origin proxy |

## Content delivery: content-as-repo

| Step | Implementation |
| --- | --- |
| Maintain | In-repo JSON under `content/` |
| Validate | JSON Schema + CI scripts |
| Import | `scripts/seed` or admin import, idempotent upsert |
| Serve | `GET /content/bootstrap` (full pull) + per-resource endpoints |
| Version | `content_version` + `min_app_version` + `checksum` |

## Deployment

Single-machine Docker Compose (1C1G and up); `docker compose up` starts it; secrets go only
through environment variables. Four independent compose files under `deploy/`
(`mongo` / `api` / `web` / `admin`), all on `network_mode: host`; the `web` container serves
build output and proxies `/api/` to `127.0.0.1:8000`. Cost ≈ ¥0/month on your own server.

## Next steps

- Full design docs → [repo `docs/`](https://gitee.com/perry-space/study-club/tree/master/docs)
- What it is → [What is Study Club](./what.md)
- Run it locally → [Quick Start](./quick-start.md)
