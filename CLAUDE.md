# CLAUDE.md — HobbyHub

## Project
Cross-platform Flutter app: a social cataloguing app ("Letterboxd, but for movies + TV series + books + games"). Solo student project, strictly MVP-focused.

## Stack & environment
- Flutter/Dart app. Developed on Windows in VS Code. Test targets: Android phone (primary), Windows desktop (secondary).
- Backend: Supabase — Postgres, Auth, Row Level Security (built in Phase 3).
- External media data: TMDb (movies + TV), Open Library (books), IGDB (games).
- Python is used ONLY for API prototype scripts and a future ML recommendation service — never inside the app itself.

## Locked product decisions — do not re-litigate
- One generic status enum shared by all four media types: `planned | in_progress | completed | dropped`. The UI translates wording per type ("Want to watch", "Reading", "Played"…).
- Library model: exactly ONE `logs` row per (user, media item). Rewatches/rereads/replays are a `times_completed` counter. A Letterboxd-style dated diary is deferred to v2.
- Ratings: 0.5–5.0 stars in half-star steps. Media detail pages show a community average computed over `logs.rating`.
- Favorites: a 4-cover showcase per media type (16 covers total), enforced by PK `(user_id, media_type, position)`.
- Auth: email/password only in MVP (Google sign-in later). UI is English-only, but keep all strings centralized so Flutter l10n can be added later.
- Explicitly OUT of MVP — do not build even if it seems easy: episode-level TV tracking, custom lists, likes/comments on reviews, push notifications, private profiles.

## Source of truth
- `docs/hobbyhub_phase0_product_definition.md` — full MVP scope, screen map, user flows, and database schema. Read it before any structural change.

## Status
- Phase 0 complete (decisions locked 2026-07-04). Next: Phase 2 (explore TMDb / Open Library / IGDB with Python scripts), then Phase 3 (Supabase schema + RLS).

## Conventions
- To be filled in as the codebase grows: state management choice, folder layout, lint rules, commit style.
