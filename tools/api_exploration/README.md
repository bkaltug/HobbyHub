# API exploration scripts (Phase 2)

Small standalone Python scripts to explore HobbyHub's three external media
APIs — TMDb (movies + TV), Open Library (books), IGDB (games) — and prove
that each source maps cleanly onto the unified `media_items` schema
(`docs/product_definition.md`, section 6) before any Dart is written.

These scripts never ship with the app; they are throwaway research tools.

## Setup

1. Install dependencies (Python 3.10+):

   ```sh
   cd tools/api_exploration
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and fill in your keys:

   - `TMDB_READ_TOKEN` — the v4 "API Read Access Token" from
     <https://www.themoviedb.org/settings/api>
   - `TWITCH_CLIENT_ID` / `TWITCH_CLIENT_SECRET` — a Twitch developer app
     from <https://dev.twitch.tv/console/apps> (IGDB authenticates via Twitch)

   Open Library needs no key.

3. `.env` and the IGDB token cache (`.igdb_token.json`) are git-ignored.
   Raw API responses land in `samples/` for later reference.

## Usage

```sh
python explore_tmdb.py movie "inception"
python explore_tmdb.py tv "breaking bad"
python explore_openlibrary.py "dune"
python explore_igdb.py "zelda"
```

Each script prints the top 5 search results, fetches details for the first
one, maps it to a `MediaItem` (see `mapping.py`), and saves the raw JSON
responses into `samples/`.