# What is Study Club

> User- and contributor-facing read. Full design:
> [01-1 Project overview & positioning](https://gitee.com/perry-space/study-club/blob/master/docs/01-产品规划/01-项目概述与定位.md) (Gitee).

## One-line positioning

**Learn Chinese characters from your textbook** — an in-class literacy + classical-poetry
starter for primary school grades 1–6, using a gamified approach to "learn and forget".

Study Club (study-club) is **free, open source and self-hostable**. Current version `0.1.0`
(first working release).

## Target users

| Role | Who | Main need |
| --- | --- | --- |
| **Student** (primary) | Kids aged 6–12 | Fun, achievement, visible progress |
| **Parent** | Supervisor, companion | How the child is doing, time spent |
| **Teacher** (optional) | Chinese teacher | Assign work, see class mastery |
| **Content ops** | Team / community | Maintain and grow content efficiently |

> The child is the main user; the parent is the supervisor. Satisfy both "the child wants to
> play" and "the parent can see results".

## Scope — does / does not do

| Does | Does not do |
| --- | --- |
| In-class literacy (standard list + self-authored units) | Other subjects (English / math) |
| Classical-poetry starter and recitation | Writing techniques, comprehension drills |
| Gamified practice and review scheduling | Live classes, one-to-one tutoring |
| Parent-visible learning reports | Hardware, teaching aids |

## Three defining traits

- **Free & open** — no paywall, no membership, no ads, no in-app purchase.
- **Open source** — code MIT; content and docs CC BY-SA 4.0.
- **Self-hostable** — the backend runs on your own server with "light" duties only.

## Current state

| Module | Content |
| --- | --- |
| **Student / parent app** | `apps/web`: Vue 3 + Vite + Pinia + PWA; three responsive tiers; map, flashcards, levels, daily tasks, review, mistakes, poems, stories, reports, settings |
| **Cloud backend** | `apps/api`: Python 3.12 + FastAPI + MongoDB 7; content, invite-code identity, profiles, learning & review, reports, stats, feedback, assets, optional encrypted sync |
| **Admin console** | `apps/admin`: Vue 3 + Element Plus; single admin (internal tool) |
| **Content repo** | `content/`: JSON + JSON Schema; `scripts/seed` imports into MongoDB |
| **Deploy** | `deploy/`: four independent compose files + nginx reverse proxy |
| **Core** | `packages/core` (zero-platform, subject-agnostic), `packages/subject-hanzi`, `packages/tokens` |

Content scale (current): characters 83 · poems 3 · units 7 · levels 14 · stories & rhymes 5 · badges 7.

> ⚠️ **Content volume is the biggest current gap** — the system scales, the content does not yet.

## Tech stack at a glance

| Layer | Choice |
| --- | --- |
| Frontend | Vue 3 + TypeScript + Vite + Pinia + vue-router + PWA |
| Backend | Python 3.12 + FastAPI + MongoDB 7 |
| Identity | Invite code + passcode (Argon2id / JWT / Ed25519) |
| Content delivery | In-repo JSON → MongoDB → `/content/*` API |
| Deploy | Docker Compose per-service + `network_mode: host` + nginx |

## Key concepts

- **Server-authoritative**: data, profiles, progress and content use the server as the single source of truth.
- **Content-as-repo**: content is separated from code; contributors only edit JSON.
- **Invite-code identity**: invite code + passcode — no phone, no WeChat, no corporate entity.
- **Hidden capabilities**: entity-dependent features carry contracts but stay disabled and unbundled.

## Keep reading & contact

- [Quick Start](./quick-start.md) · [Architecture Overview](./architecture.md)
- Full design docs → repo [`docs/`](https://gitee.com/perry-space/study-club/tree/master/docs)
- Contact **perry@perryspace.club** · Code MIT · Content CC BY-SA 4.0
