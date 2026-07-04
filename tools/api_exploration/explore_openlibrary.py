"""Explore the Open Library API (books) and map one result to MediaItem.

Usage:
    python explore_openlibrary.py "dune"

Open Library needs no API key, only an identifying User-Agent header.
"""

import json
import re
import sys
from pathlib import Path

import requests

from mapping import MediaItem, pretty_print

HERE = Path(__file__).resolve().parent
SAMPLES_DIR = HERE / "samples"
HEADERS = {"User-Agent": "HobbyHub-dev/0.1 (student project)"}

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def save_sample(filename: str, payload: dict) -> None:
    SAMPLES_DIR.mkdir(exist_ok=True)
    path = SAMPLES_DIR / filename
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  (raw JSON saved to samples/{filename})")


def get_json(url: str, params: dict | None = None) -> dict:
    response = requests.get(url, headers=HEADERS, params=params, timeout=30)
    if response.status_code != 200:
        sys.exit(f"Open Library request failed with HTTP {response.status_code}: {response.text[:300]}")
    return response.json()


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit('Usage: python explore_openlibrary.py "dune"')

    query = sys.argv[1]
    print(f'Searching Open Library for "{query}"...')
    search = get_json("https://openlibrary.org/search.json", {"q": query, "limit": 5})
    save_sample(f"openlibrary_search_{slugify(query)}.json", search)

    docs = search.get("docs", [])[:5]
    if not docs:
        sys.exit(f'No Open Library results for "{query}".')

    print(f"\nTop {len(docs)} results:")
    for d in docs:
        authors = ", ".join(d.get("author_name", [])) or "(unknown author)"
        print(f'  {d.get("title")} — {authors} ({d.get("first_publish_year", "????")})')

    first = docs[0]
    work_key = first["key"]  # e.g. "/works/OL893415W"
    print(f"\nFetching work details for the first result ({work_key})...")
    work = get_json(f"https://openlibrary.org{work_key}.json")
    save_sample(f"openlibrary_work_{slugify(work_key)}.json", work)

    # description can be a plain string, {"type": ..., "value": ...}, or absent
    description = work.get("description")
    if isinstance(description, dict):
        description = description.get("value")

    cover_i = first.get("cover_i")
    item = MediaItem(
        media_type="book",
        source="openlibrary",
        external_id=work_key,
        title=first.get("title"),
        cover_url=f"https://covers.openlibrary.org/b/id/{cover_i}-L.jpg" if cover_i else None,
        release_year=first.get("first_publish_year"),
        creators=first.get("author_name", []),
        genres=(work.get("subjects") or [])[:5],
        extra={"description": description} if description else {},
    )
    pretty_print(item)


if __name__ == "__main__":
    main()