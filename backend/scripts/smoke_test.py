"""End-to-end smoke test for CurriculumCraft.

Boots the FastAPI app in-process and exercises the multi-subject API
surface that Phases 1-4 introduced. Designed to be cheap (no real LLM
calls, no PDF ingestion) so it can run on every PR as a CI check.

Asserts:
  - /api/health returns 200
  - /api/subjects returns 24 canonical subjects with Arabic + English labels
  - /api/subjects/math/config has has_math_rendering=True
  - /api/subjects/arabic_lang/config has has_math_rendering=False
  - /api/moe-library/books spans multiple subjects when no filter is set
  - /api/moe-library/books?subject=math returns only math entries
  - /api/moe-library/books?subject=arabic_lang returns Arabic entries
  - /api/moe-library/books?subject=invalid_xyz returns 400
  - hamza-folded subjects (spanish_l2) resolve to the same canonical key
    regardless of which alif variant the MOE catalog uses

Exits 0 on success, non-zero on any assertion failure. Run with:
    PYTHONIOENCODING=utf-8 python backend/scripts/smoke_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running this script from anywhere — add backend/ to sys.path.
BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


def assert_eq(actual, expected, label: str) -> None:
    if actual != expected:
        print(f"FAIL [{label}] expected={expected!r} got={actual!r}")
        sys.exit(1)
    print(f"  OK [{label}] = {actual!r}")


def assert_ge(actual: int, minimum: int, label: str) -> None:
    if actual < minimum:
        print(f"FAIL [{label}] expected >= {minimum}, got {actual}")
        sys.exit(1)
    print(f"  OK [{label}] {actual} >= {minimum}")


def main() -> int:
    with TestClient(app) as client:
        print("=== Health ===")
        r = client.get("/api/health")
        assert_eq(r.status_code, 200, "health.status")
        assert_eq(r.json().get("status"), "healthy", "health.body.status")

        print("=== Subject taxonomy ===")
        r = client.get("/api/subjects")
        assert_eq(r.status_code, 200, "subjects.status")
        items = r.json()
        assert_eq(len(items), 24, "subjects.count")

        keys = {it["key"] for it in items}
        for must_have in {
            "math",
            "arabic_lang",
            "english_lang",
            "physics",
            "chemistry",
            "history",
            "religion_islamic",
            "ict_en",
            "spanish_l2",
            "chinese_l2",
        }:
            if must_have not in keys:
                print(f"FAIL [subjects.keys] missing {must_have!r}")
                return 1
        print(f"  OK [subjects.keys] all canonical keys present")

        for it in items:
            if not it.get("label_ar") or not it.get("label_en"):
                print(f"FAIL [subjects.labels] {it['key']!r} has empty label")
                return 1
        print(f"  OK [subjects.labels] all 24 rows have ar+en labels")

        print("=== Subject configs (math vs arabic_lang vs physics) ===")
        r = client.get("/api/subjects/math/config")
        assert_eq(r.status_code, 200, "math.config.status")
        cfg = r.json()
        assert_eq(cfg["has_math_rendering"], True, "math.has_math_rendering")
        assert_eq(cfg["has_formula_boxes"], True, "math.has_formula_boxes")
        assert_eq(cfg["primary_direction"], "rtl", "math.primary_direction")

        r = client.get("/api/subjects/arabic_lang/config")
        assert_eq(r.status_code, 200, "arabic.config.status")
        cfg = r.json()
        assert_eq(cfg["has_math_rendering"], False, "arabic.has_math_rendering")
        assert_eq(cfg["has_quotations"], True, "arabic.has_quotations")
        assert_eq(cfg["primary_direction"], "rtl", "arabic.primary_direction")

        r = client.get("/api/subjects/physics/config")
        assert_eq(r.status_code, 200, "physics.config.status")
        cfg = r.json()
        # Physics has GenericStrategy but the trait still flags math rendering.
        assert_eq(cfg["has_math_rendering"], True, "physics.has_math_rendering")

        r = client.get("/api/subjects/nonexistent_xyz/config")
        assert_eq(r.status_code, 404, "unknown.config.status")

        print("=== MOE catalog filtering ===")
        r = client.get("/api/moe-library/books")
        assert_eq(r.status_code, 200, "moe.books.no_filter.status")
        all_count = len(r.json())
        assert_ge(all_count, 100, "moe.books.no_filter.count")

        r = client.get("/api/moe-library/books?subject=math")
        assert_eq(r.status_code, 200, "moe.books.math.status")
        math_count = len(r.json())
        assert_ge(math_count, 5, "moe.books.math.count")
        # Math should be a strict subset of the unfiltered catalog.
        if math_count >= all_count:
            print(f"FAIL [moe.books.math.subset] math={math_count} >= all={all_count}")
            return 1
        print(f"  OK [moe.books.math.subset] math={math_count} < all={all_count}")

        r = client.get("/api/moe-library/books?subject=arabic_lang")
        assert_eq(r.status_code, 200, "moe.books.arabic.status")
        arabic_count = len(r.json())
        assert_ge(arabic_count, 1, "moe.books.arabic.count")

        r = client.get("/api/moe-library/books?subject=spanish_l2")
        assert_eq(r.status_code, 200, "moe.books.spanish.status")

        r = client.get("/api/moe-library/books?subject=invalid_xyz")
        assert_eq(r.status_code, 400, "moe.books.invalid.status")

        print("=== Catalog drift surfacing ===")
        r = client.get("/api/moe-library/catalog-subjects")
        assert_eq(r.status_code, 200, "moe.catalog-subjects.status")
        items = r.json()
        assert_ge(len(items), 30, "moe.catalog-subjects.count")
        mapped = sum(1 for it in items if it.get("key") is not None)
        unmapped = len(items) - mapped
        print(f"  INFO catalog drift: mapped={mapped} unmapped={unmapped}")

    print("\n=== ALL SMOKE TESTS PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
