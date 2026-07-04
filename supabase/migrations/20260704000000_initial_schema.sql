-- ============================================================================
-- HobbyHub — migration 0001: initial schema
-- Phase 3, Part B
--
-- How to apply: Supabase Dashboard → SQL Editor → paste this whole file → Run.
-- Design source of truth: docs/product_definition.md, section 6.
--
-- Trade-off notes are inline as comments — this file doubles as documentation.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 0. Extensions
-- ----------------------------------------------------------------------------
-- moddatetime gives us a ready-made trigger that stamps updated_at on UPDATE.
create extension if not exists moddatetime with schema extensions;

-- ----------------------------------------------------------------------------
-- 1. Enums — one shared vocabulary for all four hobbies
-- ----------------------------------------------------------------------------
create type public.media_type as enum ('movie', 'tv', 'book', 'game');
create type public.media_source as enum ('tmdb', 'openlibrary', 'igdb');
-- Generic statuses; the Flutter UI translates them per media type
-- ("planned" renders as "Want to watch" / "Want to read" / "Want to play").
create type public.log_status as enum ('planned', 'in_progress', 'completed', 'dropped');

-- ----------------------------------------------------------------------------
-- 2. profiles — one row per auth user
-- ----------------------------------------------------------------------------
create table public.profiles (
  id           uuid primary key references auth.users (id) on delete cascade,
  username     text not null unique check (username ~ '^[a-z0-9_]{3,20}$'),
  display_name text,
  avatar_url   text,
  bio          text check (bio is null or char_length(bio) <= 300),
  created_at   timestamptz not null default now()
);

-- Auto-create a profile the moment a user signs up.
-- security definer: runs as the function owner so it can insert past RLS.
-- If the app passes a username in signup metadata we use it; if it's missing,
-- invalid, or already taken, we fall back to a unique placeholder so signup
-- NEVER fails — the "pick username" screen then updates it.
create function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
declare
  proposed text := lower(nullif(new.raw_user_meta_data ->> 'username', ''));
  fallback text := 'user_' || substr(replace(new.id::text, '-', ''), 1, 10);
begin
  if proposed is null
     or proposed !~ '^[a-z0-9_]{3,20}$'
     or exists (select 1 from public.profiles where username = proposed) then
    proposed := fallback;
  end if;

  insert into public.profiles (id, username)
  values (new.id, proposed);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

alter table public.profiles enable row level security;

-- MVP has no private profiles, so everyone can read every profile.
create policy "profiles are readable by everyone"
  on public.profiles for select
  using (true);

create policy "users can update their own profile"
  on public.profiles for update
  using ((select auth.uid()) = id)
  with check ((select auth.uid()) = id);

-- No insert policy: the trigger above is the only writer.
-- No delete policy: deleting the auth user cascades here (account deletion
-- is a server-side concern we wire up in the release phase).

-- ----------------------------------------------------------------------------
-- 3. follows — the social graph
-- ----------------------------------------------------------------------------
create table public.follows (
  follower_id  uuid not null references public.profiles (id) on delete cascade,
  following_id uuid not null references public.profiles (id) on delete cascade,
  created_at   timestamptz not null default now(),
  primary key (follower_id, following_id),
  check (follower_id <> following_id)          -- no self-follow
);

-- The PK already indexes follower_id lookups ("who do I follow");
-- this covers the reverse direction ("who follows me").
create index follows_following_id_idx on public.follows (following_id);

alter table public.follows enable row level security;

create policy "follows are readable by everyone"
  on public.follows for select
  using (true);

create policy "users can follow as themselves"
  on public.follows for insert
  with check ((select auth.uid()) = follower_id);

create policy "users can unfollow"
  on public.follows for delete
  using ((select auth.uid()) = follower_id);

-- ----------------------------------------------------------------------------
-- 4. media_items — our cache of anything a user has touched
-- ----------------------------------------------------------------------------
create table public.media_items (
  id           uuid primary key default gen_random_uuid(),
  media_type   public.media_type not null,
  source       public.media_source not null,
  external_id  text not null,                  -- the item's id in the source API
  title        text not null,
  cover_url    text,
  release_year int,
  creators     text[] not null default '{}',   -- director / author / developer
  genres       text[] not null default '{}',
  extra        jsonb not null default '{}'::jsonb,
  cached_at    timestamptz not null default now(),
  unique (source, external_id)                 -- one cache row per API record
);

alter table public.media_items enable row level security;

create policy "media items are readable by everyone"
  on public.media_items for select
  using (true);

-- Any signed-in user may cache a new item (this happens when they log
-- something we have not seen before).
create policy "signed-in users can cache media items"
  on public.media_items for insert
  to authenticated
  with check (true);

-- Deliberately NO update/delete policies: the cache is write-once from
-- clients, so one user can never vandalize the title or cover that everyone
-- else sees. The Flutter app must insert with "ignore duplicates" semantics
-- (ON CONFLICT DO NOTHING). Refreshing stale metadata becomes a server-side
-- job later if we ever need it.

-- ----------------------------------------------------------------------------
-- 5. logs — the heart of the app (library model, decision D1)
-- ----------------------------------------------------------------------------
create table public.logs (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references public.profiles (id) on delete cascade,
  media_item_id   uuid not null references public.media_items (id) on delete cascade,
  status          public.log_status not null default 'planned',
  -- 0.5 to 5.0 in half-star steps: rating*2 must be a whole number.
  rating          numeric(2,1) check (
                    rating is null
                    or (rating between 0.5 and 5.0 and rating * 2 = floor(rating * 2))
                  ),
  review          text check (review is null or char_length(review) <= 5000),
  finished_on     date,
  times_completed int not null default 0 check (times_completed >= 0),
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (user_id, media_item_id)              -- ONE row per user per item
);

-- The home feed query is "logs of people I follow, newest first":
create index logs_user_updated_idx on public.logs (user_id, updated_at desc);
-- Community average rating groups by item:
create index logs_media_item_idx on public.logs (media_item_id);

create trigger logs_set_updated_at
  before update on public.logs
  for each row execute procedure extensions.moddatetime (updated_at);

alter table public.logs enable row level security;

-- Public profiles => public logs (also what powers community averages).
create policy "logs are readable by everyone"
  on public.logs for select
  using (true);

create policy "users can insert their own logs"
  on public.logs for insert
  with check ((select auth.uid()) = user_id);

create policy "users can update their own logs"
  on public.logs for update
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy "users can delete their own logs"
  on public.logs for delete
  using ((select auth.uid()) = user_id);

-- ----------------------------------------------------------------------------
-- 6. favorites — the 4-cover showcase, one per media type
-- ----------------------------------------------------------------------------
create table public.favorites (
  user_id       uuid not null references public.profiles (id) on delete cascade,
  media_type    public.media_type not null,
  media_item_id uuid not null references public.media_items (id) on delete cascade,
  position      int not null check (position between 1 and 4),
  primary key (user_id, media_type, position), -- max 4 slots per hobby, by design
  unique (user_id, media_item_id)              -- same item cannot fill two slots
);

-- Guard: a slot's media_type must match the item it points to.
create function public.check_favorite_media_type()
returns trigger
language plpgsql
as $$
begin
  if (select media_type from public.media_items where id = new.media_item_id)
     is distinct from new.media_type then
    raise exception 'favorite media_type does not match the media item';
  end if;
  return new;
end;
$$;

create trigger favorites_type_guard
  before insert or update on public.favorites
  for each row execute function public.check_favorite_media_type();

alter table public.favorites enable row level security;

create policy "favorites are readable by everyone"
  on public.favorites for select
  using (true);

create policy "users can add their own favorites"
  on public.favorites for insert
  with check ((select auth.uid()) = user_id);

create policy "users can update their own favorites"
  on public.favorites for update
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy "users can remove their own favorites"
  on public.favorites for delete
  using ((select auth.uid()) = user_id);

-- ----------------------------------------------------------------------------
-- 7. Community average rating (decision D3) — a view, not a table
-- ----------------------------------------------------------------------------
-- Computed on demand; always correct, zero maintenance. If HobbyHub ever has
-- millions of logs we revisit this with counter columns — not an MVP problem.
-- security_invoker makes the view respect the RLS of the logs table.
create view public.media_item_stats
with (security_invoker = true) as
select
  media_item_id,
  round(avg(rating), 1) as avg_rating,
  count(rating)         as ratings_count
from public.logs
where rating is not null
group by media_item_id;

-- ----------------------------------------------------------------------------
-- Sanity checks (optional — run these after the migration succeeds)
-- ----------------------------------------------------------------------------
-- select table_name, row_security_active(table_name::regclass) as rls_on
--   from information_schema.tables
--   where table_schema = 'public' and table_type = 'BASE TABLE';
--
-- insert into public.media_items (media_type, source, external_id, title)
--   values ('movie', 'tmdb', '27205', 'Inception');   -- run as service role
-- select * from public.media_items;