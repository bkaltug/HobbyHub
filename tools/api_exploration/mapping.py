"""MediaItem: an in-memory mirror of the `media_items` table.

See docs/product_definition.md, section 6. Each exploration script maps one
raw API response into this shape to prove the unified schema works for all
three sources before any Dart is written.
"""

from dataclasses import dataclass, field


@dataclass
class MediaItem:
    media_type: str                 # movie | tv | book | game
    source: str                     # tmdb | openlibrary | igdb
    external_id: str                # the item's id in the source API
    title: str
    cover_url: str | None
    release_year: int | None
    creators: list[str] = field(default_factory=list)   # director / author / developer
    genres: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)           # type-specific leftovers


def pretty_print(item: MediaItem) -> None:
    """Print a MediaItem as an aligned block, truncating long extra values."""
    print()
    print(f"MediaItem  [{item.source} -> {item.media_type}]")
    print("-" * 64)
    print(f"  external_id  : {item.external_id}")
    print(f"  title        : {item.title}")
    print(f"  cover_url    : {item.cover_url}")
    print(f"  release_year : {item.release_year}")
    print(f"  creators     : {', '.join(item.creators) if item.creators else '(none)'}")
    print(f"  genres       : {', '.join(item.genres) if item.genres else '(none)'}")
    if item.extra:
        print("  extra        :")
        for key, value in item.extra.items():
            text = str(value)
            if len(text) > 300:
                text = text[:300] + "..."
            print(f"    {key}: {text}")
    else:
        print("  extra        : (empty)")
    print("-" * 64)