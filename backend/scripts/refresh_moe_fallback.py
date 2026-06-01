"""Refresh the bundled MOE catalog fallback fixtures.

Fetches both /books/books.json and /cha/books.json from MOE upstream
using the production MOELibraryService (with cookie warmup) and writes
them as plain JSON arrays to backend/seeds/.

The deployed backend uses these fixtures whenever the live upstream
fetch fails — typically because the HF Space's egress IPs are rejected
by MOE's Azure-fronted edge. Bundled fixtures make the app functional
end-to-end even if MOE upstream is permanently unreachable from prod.

Run from a development machine that CAN reach MOE upstream (e.g. a home
IP, not a datacenter):

    PYTHONIOENCODING=utf-8 python backend/scripts/refresh_moe_fallback.py

Then commit the updated backend/seeds/moe_books_fallback.json and
backend/seeds/moe_assessments_fallback.json files.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services.moe_library_service import MOELibraryService  # noqa: E402

SEEDS_DIR = BACKEND / "seeds"


async def main() -> int:
    SEEDS_DIR.mkdir(parents=True, exist_ok=True)
    svc = MOELibraryService()

    # Force a fresh fetch by ignoring cached files (the cache layer
    # short-circuits this path otherwise).
    for cache_path in (svc.CACHE_FILE, svc.ASSESSMENTS_CACHE_FILE):
        try:
            cache_path.unlink(missing_ok=True)
        except OSError:
            pass

    print("Fetching MOE books catalog from upstream...")
    books = await svc.fetch_catalog()
    books_out = SEEDS_DIR / "moe_books_fallback.json"
    books_out.write_text(
        json.dumps(books, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  wrote {books_out} — {len(books)} records, {books_out.stat().st_size:,} bytes")

    print("Fetching MOE assessments catalog from upstream...")
    assessments = await svc.fetch_assessments_catalog()
    assessments_out = SEEDS_DIR / "moe_assessments_fallback.json"
    assessments_out.write_text(
        json.dumps(assessments, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"  wrote {assessments_out} — {len(assessments)} records, "
        f"{assessments_out.stat().st_size:,} bytes"
    )

    print("\nDone. Commit the seed JSON files so they ship with the next deploy.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
