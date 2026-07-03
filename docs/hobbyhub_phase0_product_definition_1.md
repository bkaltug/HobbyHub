# HobbyHub — Phase 0: Product Definition

**Status:** Decisions locked — commit under `docs/`; screen sketches still pending
**Last updated:** 2026-07-04

---

## 1. One-sentence pitch

HobbyHub is a social cataloguing app — Letterboxd's logic extended to four media types. Users log the movies, TV series, books, and games they consume; rate and review them; and follow friends to see their activity.

---

## 2. MVP scope — what v1.0 DOES

### Accounts & profiles
- Email/password sign-up and sign-in. (Google sign-in: stretch goal — see decision D2.)
- Unique username chosen at sign-up.
- Profile page: avatar, display name, bio, a favorites showcase **for each hobby** (4 covers per media type — the Letterboxd signature, × 4), counters (completed items per media type, followers, following).

### Search & media pages
- One search screen with four tabs: **Movies · TV · Books · Games**.
- Live search against TMDb (movies + TV), Open Library (books), IGDB (games).
- Media detail page: cover, title, year, creator (director / show creator / author / developer), genres, synopsis, community average rating (decision D3), and action buttons (log / rate / add to Planned).

### Logging — the core loop
- Status per item, the **same four values for every media type**: `Planned · In Progress · Completed · Dropped`. The UI translates per type ("Want to watch", "Reading", "Played"…), but the data model stays unified — this one trick keeps a 4-media-type app simple.
- Rating: 0.5–5 stars in half-star steps (Letterboxd scale).
- Review: optional free text.
- Finished date: optional.
- Times-completed counter (covers rewatch / reread / replay).

### Library
- "My Library" screen: everything the user has logged, filterable by media type and by status.
- The `Planned` filter **is** the watchlist/backlog — no separate feature needed.

### Social
- Follow / unfollow users.
- View any user's public profile.
- Home feed: recent activity (logged, rated, reviewed) from followed users, newest first.

### Settings
- Edit profile, sign out, **delete account** (Google Play requires in-app account deletion — not optional).

---

## 3. Explicitly OUT of MVP — the v2 backlog

Writing these down gives you permission to stop thinking about them:

- Likes and comments on reviews.
- Custom lists (beyond the built-in Planned/watchlist).
- **Episode-level TV tracking.** MVP tracks a series as one item. Per-episode tracking is a scope monster — defer it deliberately.
- Push notifications.
- Stats pages / "year in review".
- ML recommendations (this is Phase 11, your Python playground).
- Private profiles.
- Report & block. Not needed for internal testing, but Google Play's User-Generated Content policy requires it **before public launch** — schedule for v1.1.
- iOS release (code stays cross-platform; ship Android first, test on Windows desktop).

---

## 4. Screen map (10 screens)

| # | Screen | Notes |
|---|--------|-------|
| 1 | Welcome / Sign in / Sign up | plus a "pick username" step after sign-up |
| 2 | Home | activity feed of followed users |
| 3 | Search | 4 tabs, results list (cover, title, year) |
| 4 | Media detail | cover, metadata, synopsis, action buttons |
| 5 | Log sheet | bottom-sheet modal: status, stars, date, review |
| 6 | Profile | one widget for self **and** others; self shows *Edit*, others show *Follow* |
| 7 | Library | filters: media type × status |
| 8 | Followers / Following | simple user list |
| 9 | Edit profile | avatar, display name, bio, favorites picker per media type |
| 10 | Settings | sign out, delete account |

**Bottom navigation:** Home · Search · **+** (opens Log flow) · Library · Profile

**Navigation flow in words:** Auth screens lead into the app shell. From *Search* → *Media detail* → *Log sheet*. From *Home*, tapping a card opens *Media detail*; tapping a username opens that user's *Profile*. From *Profile* → *Followers/Following*, *Edit profile*, or *Settings*. The **+** tab opens search-then-log directly.

---

## 5. Core user flows — sketch these three

- **Flow A, first run:** Welcome → Sign up → Pick username → empty Home with a "search for something you love" prompt → Search → Detail → Log → back on Home, sees own first activity.
- **Flow B, the daily loop:** Search → Detail → Log sheet → save → entry appears on own Profile and in followers' feeds.
- **Flow C, social:** Home feed card → tap username → their Profile → Follow → their future activity appears in Home.

Sketch rule: boxes and labels only. Paper + phone photo, or Excalidraw. If a sketch takes more than 5 minutes, you're designing, not sketching.

---

## 6. Data model — first draft (PostgreSQL / Supabase)

### `profiles`
| column | type | notes |
|---|---|---|
| id | uuid PK | equals Supabase `auth.users.id` |
| username | text UNIQUE NOT NULL | lowercase, 3–20 chars |
| display_name | text | |
| avatar_url | text | |
| bio | text | |
| created_at | timestamptz | |

### `follows`
| column | type | notes |
|---|---|---|
| follower_id | uuid FK → profiles | |
| following_id | uuid FK → profiles | |
| created_at | timestamptz | |
| | | PRIMARY KEY (follower_id, following_id) |

### `media_items` — cache of anything a user has touched
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| media_type | enum | movie \| tv \| book \| game |
| source | enum | tmdb \| openlibrary \| igdb |
| external_id | text | the item's id in the source API |
| title | text | |
| cover_url | text | |
| release_year | int | |
| creators | text[] | director / author / developer |
| genres | text[] | |
| extra | jsonb | anything type-specific (page count, platforms…) |
| cached_at | timestamptz | |
| | | UNIQUE (source, external_id) |

### `logs` — one row per user per item (see decision D1)
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK → profiles | |
| media_item_id | uuid FK → media_items | |
| status | enum | planned \| in_progress \| completed \| dropped |
| rating | numeric(2,1) NULL | 0.5–5.0, half steps |
| review | text NULL | |
| finished_on | date NULL | |
| times_completed | int DEFAULT 0 | rewatch / reread / replay counter |
| created_at, updated_at | timestamptz | |
| | | UNIQUE (user_id, media_item_id) |

### `favorites` — a 4-cover showcase per media type
| column | type | notes |
|---|---|---|
| user_id | uuid FK → profiles | |
| media_type | enum | movie \| tv \| book \| game |
| media_item_id | uuid FK → media_items | |
| position | int | 1–4 within each media type |
| | | PRIMARY KEY (user_id, media_type, position) |

`media_type` is stored here even though it also lives on `media_items`: that way the primary key itself enforces "max 4 favorites per hobby" (16 total). The app just keeps it consistent with the item it points to.

### The feed is just a query
```sql
select l.*, m.title, m.cover_url, m.media_type, p.username, p.avatar_url
from logs l
join media_items m on m.id = l.media_item_id
join profiles p  on p.id = l.user_id
where l.user_id in (select following_id from follows where follower_id = :me)
order by l.updated_at desc
limit 20;
```
This single query is why we chose Supabase/Postgres over Firestore.

---

## 7. Decisions — locked 2026-07-04

- **D1 — Library vs diary model: LIBRARY.** One `logs` row per user+item for v1; rewatches are a counter. A Letterboxd-style `diary_entries` table is planned for v2 and can be added without breaking this model.
- **D2 — Google sign-in: NOT in MVP.** Email/password only; Google sign-in comes in the polish phase.
- **D3 — Community average rating: IN MVP.** Detail pages show the average HobbyHub rating, computed as a simple aggregate over `logs.rating` for that item.
- **D4 — App language: ENGLISH ONLY.** Keep all UI strings centralized so Flutter l10n (Turkish etc.) can be retrofitted later without a rewrite.

---

## 8. Phase 0 — definition of done

- [ ] This document read, edited, and committed to the repo (`docs/`)
- [x] Decisions D1–D4 answered and recorded here
- [ ] Low-fi sketches of screens 2–7 exist (photos or Excalidraw file in `docs/sketches/`)
- [ ] Data model reviewed once more (real implementation happens in Phase 3)
