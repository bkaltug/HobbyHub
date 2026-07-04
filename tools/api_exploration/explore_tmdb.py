"""Explore the TMDb API (movies + TV) and map one result to MediaItem.

Usage:
    python explore_tmdb.py movie "inception"
    python explore_tmdb.py tv "breaking bad"
"""

import json
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

from mapping import MediaItem, pretty_print

HERE = Path(__file__).resolve().parent
SAMPLES_DIR = HERE / "samples"
BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

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


def save_sample(filename: str, payload: dict) -> None:
    SAMPLES_DIR.mkdir(exist_ok=True)
    path = SAMPLES_DIR / filename
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  (raw JSON saved to samples/{filename})")


def get_json(url: str, headers: dict, params: dict | None = None) -> dict:
    response = requests.get(url, headers=headers, params=params, timeout=30)
    if response.status_code != 200:
        sys.exit(f"TMDb request failed with HTTP {response.status_code}: {response.text[:300]}")
    return response.json()


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in ("movie", "tv"):
        sys.exit('Usage: python explore_tmdb.py movie "inception"  |  python explore_tmdb.py tv "breaking bad"')

    media_type, query = sys.argv[1], sys.argv[2]
    token = require_env("TMDB_READ_TOKEN")
    headers = {"Authorization": f"Bearer {token}"}

    print(f'Searching TMDb {media_type} for "{query}"...')
    search = get_json(f"{BASE_URL}/search/{media_type}", headers, {"query": query})
    save_sample(f"tmdb_{media_type}_search_{slugify(query)}.json", search)

    results = search.get("results", [])[:5]
    if not results:
        sys.exit(f'No TMDb {media_type} results for "{query}".')

    print(f"\nTop {len(results)} results:")
    for r in results:
        title = r.get("title") or r.get("name")
        date = r.get("release_date") or r.get("first_air_date") or ""
        year = date[:4] if date else "????"
        print(f'  id={r["id"]:<10} {title} ({year})  vote_average={r.get("vote_average")}')

    first_id = results[0]["id"]
    print(f"\nFetching details for the first result (id={first_id})...")
    details = get_json(f"{BASE_URL}/{media_type}/{first_id}", headers, {"append_to_response": "credits"})
    save_sample(f"tmdb_{media_type}_details_{first_id}.json", details)

    if media_type == "movie":
        title = details.get("title")
        date = details.get("release_date") or ""
        creators = [c["name"] for c in details.get("credits", {}).get("crew", []) if c.get("job") == "Director"]
        extra = {"runtime": details.get("runtime")}
    else:
        title = details.get("name")
        date = details.get("first_air_date") or ""
        creators = [p["name"] for p in details.get("created_by", [])]
        extra = {"number_of_seasons": details.get("number_of_seasons")}

    poster_path = details.get("poster_path")
    item = MediaItem(
        media_type=media_type,
        source="tmdb",
        external_id=str(details["id"]),
        title=title,
        cover_url=IMAGE_BASE + poster_path if poster_path else None,
        release_year=int(date[:4]) if date[:4].isdigit() else None,
        creators=creators,
        genres=[g["name"] for g in details.get("genres", [])],
        extra=extra,
    )
    pretty_print(item)


if __name__ == "__main__":
    main()