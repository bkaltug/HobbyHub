"""Explore the IGDB API (games) and map one result to MediaItem.

Usage:
    python explore_igdb.py "zelda"

IGDB authenticates through Twitch: a client-credentials app access token is
fetched once and cached in .igdb_token.json until it expires.
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

from mapping import MediaItem, pretty_print

HERE = Path(__file__).resolve().parent
SAMPLES_DIR = HERE / "samples"
TOKEN_FILE = HERE / ".igdb_token.json"
TOKEN_URL = "https://id.twitch.tv/oauth2/token"
GAMES_URL = "https://api.igdb.com/v4/games"
COVER_BASE = "https://images.igdb.com/igdb/image/upload/t_cover_big"

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv(HERE / ".env")


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        sys.exit(
            f"Missing environment variable: {name}\n"
            f"Copy .env.example to .env in {HERE} and fill in {name}."
        )
    return value


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def save_sample(filename: str, payload) -> None:
    SAMPLES_DIR.mkdir(exist_ok=True)
    path = SAMPLES_DIR / filename
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  (raw JSON saved to samples/{filename})")


def get_token(client_id: str, client_secret: str) -> str:
    """Return a cached app access token, refreshing it via Twitch when expired."""
    if TOKEN_FILE.exists():
        try:
            cached = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
            if cached.get("expires_at", 0) > time.time() + 60:
                print("Using cached IGDB token from .igdb_token.json")
                return cached["access_token"]
        except (json.JSONDecodeError, OSError, KeyError):
            pass  # unreadable cache: just fetch a fresh token

    print("Requesting a new IGDB app access token from Twitch...")
    response = requests.post(
        TOKEN_URL,
        params={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        },
        timeout=30,
    )
    if response.status_code != 200:
        sys.exit(f"Twitch token request failed with HTTP {response.status_code}: {response.text[:300]}")
    data = response.json()
    token = data["access_token"]
    TOKEN_FILE.write_text(
        json.dumps({"access_token": token, "expires_at": time.time() + data.get("expires_in", 0)}),
        encoding="utf-8",
    )
    return token


def release_year(unix_ts) -> int | None:
    if not unix_ts:
        return None
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).year


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit('Usage: python explore_igdb.py "zelda"')

    query = sys.argv[1]
    client_id = require_env("TWITCH_CLIENT_ID")
    client_secret = require_env("TWITCH_CLIENT_SECRET")
    token = get_token(client_id, client_secret)

    body = (
        f'search "{query.replace(chr(34), "")}"; '
        "fields name, first_release_date, summary, cover.image_id, "
        "genres.name, involved_companies.company.name, involved_companies.developer; "
        "limit 5;"
    )
    print(f'Searching IGDB for "{query}"...')
    response = requests.post(
        GAMES_URL,
        headers={"Client-ID": client_id, "Authorization": f"Bearer {token}"},
        data=body,
        timeout=30,
    )
    if response.status_code != 200:
        sys.exit(f"IGDB request failed with HTTP {response.status_code}: {response.text[:300]}")
    games = response.json()
    save_sample(f"igdb_search_{slugify(query)}.json", games)

    if not games:
        sys.exit(f'No IGDB results for "{query}".')

    print(f"\nTop {len(games)} results:")
    for g in games:
        print(f'  {g.get("name")} ({release_year(g.get("first_release_date")) or "????"})')

    game = games[0]
    creators = [
        ic["company"]["name"]
        for ic in game.get("involved_companies", [])
        if ic.get("developer") and ic.get("company", {}).get("name")
    ]
    image_id = game.get("cover", {}).get("image_id")
    summary = game.get("summary")
    item = MediaItem(
        media_type="game",
        source="igdb",
        external_id=str(game["id"]),
        title=game.get("name"),
        cover_url=f"{COVER_BASE}/{image_id}.jpg" if image_id else None,
        release_year=release_year(game.get("first_release_date")),
        creators=creators,
        genres=[g["name"] for g in game.get("genres", [])],
        extra={"summary": summary} if summary else {},
    )
    pretty_print(item)


if __name__ == "__main__":
    main()