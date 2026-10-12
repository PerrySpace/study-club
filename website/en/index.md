---
layout: home

hero:
  name: Study Club
  text: Learn Chinese characters from your textbook
  tagline: In-class literacy and classical-poetry starter for primary school grades 1–6. Free, open source, self-hostable.
  image:
    src: /logo.svg
    alt: Study Club
  actions:
    - theme: brand
      text: Get Started
      link: /en/docs/quick-start
    - theme: alt
      text: Live Demo
      link: https://study.perryspace.club
    - theme: alt
      text: Gitee
      link: https://gitee.com/perry-space/study-club

features:
  - title: One account, multiple kids
    details: Each child gets an independent profile and progress — switch or archive anytime, no extra sign-up needed.
  - title: Three responsive tiers
    details: Phone (<768px), iPad (768–1279px) and desktop (≥1280px) from a single Web + PWA codebase.
  - title: Server-authoritative
    details: Learning data, child profiles, progress and content all live in server-side MongoDB as the single source of truth.
  - title: Content-as-repo
    details: Content is maintained as content/**/*.json with JSON Schema, imported into the database and served via API — no release needed to change content.
  - title: Invite-code identity
    details: Sign up and sign in with an invite code plus a self-set passcode — no phone number, no WeChat, no corporate entity.
  - title: Self-hostable
    details: Docker Compose per-service orchestration (mongo / api / web / admin) with nginx same-origin reverse proxy.
  - title: Free & open
    details: No paywall, no membership, no ads, no in-app purchase. Code under MIT, content and docs under CC BY-SA 4.0.
---

## Start here

- New to the project? Read [What is Study Club](/en/docs/what).
- Want to run it locally? Follow the [Quick Start](/en/docs/quick-start).
- Prefer the full design docs (in Chinese)? See the repository
  [`docs/`](https://gitee.com/perry-space/study-club/tree/master/docs).
