"""Read-only smoke checks for the local SourceAI Next.js/FastAPI stack."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


API_BASE = os.getenv("SOURCEAI_API_BASE", "http://127.0.0.1:8001").rstrip("/")
WEB_BASE = os.getenv("SOURCEAI_WEB_BASE", "http://127.0.0.1:3000").rstrip("/")


def read_json(path: str) -> tuple[int, Any]:
    request = urllib.request.Request(f"{API_BASE}{path}", method="GET")
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def read_text(url: str) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=15) as response:
        return response.status, response.read().decode("utf-8", "replace")


def expect_denied(path: str) -> bool:
    try:
        read_json(path)
    except urllib.error.HTTPError as exc:
        return exc.code in {401, 403}
    return False


def main() -> int:
    passed: list[str] = []
    failed: list[str] = []

    try:
        status, payload = read_json("/api/health")
        if status == 200 and payload.get("status") == "ok":
            passed.append("API liveness")
        else:
            failed.append("API liveness returned an unexpected response")
    except Exception as exc:  # noqa: BLE001
        failed.append(f"API liveness failed ({type(exc).__name__})")

    try:
        status, payload = read_json("/api/ready")
        if status == 200 and payload.get("status") == "ready":
            passed.append("API/database readiness")
        else:
            failed.append("API readiness returned an unexpected response")
    except Exception as exc:  # noqa: BLE001
        failed.append(f"API readiness failed ({type(exc).__name__})")

    sample_slug: str | None = None
    try:
        status, products = read_json("/api/products/")
        if status == 200 and isinstance(products, list) and len(products) >= 610:
            sample_slug = products[0].get("slug")
            passed.append(f"public catalog ({len(products)} products)")
        else:
            failed.append("public catalog is unexpectedly small or malformed")
    except Exception as exc:  # noqa: BLE001
        failed.append(f"public catalog failed ({type(exc).__name__})")

    try:
        _, categories = read_json("/api/categories/")
        slugs = {str(item.get("slug")) for item in categories}
        required_categories = {
            "beauty-tools-accessories",
            "creator-content-tools",
            "ecommerce-packaging-supplies",
            "educational-academic-tools",
            "fashion-accessories",
            "home-organization-storage",
            "kitchen-utility-tools",
            "laptop-pc-accessories",
            "medical-products-accessories",
            "mobile-accessories",
            "jewelry-gems-precious-metals",
            "office-desk-accessories",
            "pet-care-accessories",
            "travel-luggage-accessories",
        }
        missing_categories = required_categories - slugs
        if not missing_categories:
            passed.append("medical, precious-material, and priority categories")
        else:
            failed.append(
                "required categories are missing: "
                + ", ".join(sorted(missing_categories))
            )
    except Exception as exc:  # noqa: BLE001
        failed.append(f"category check failed ({type(exc).__name__})")

    try:
        _, countries = read_json("/api/countries/")
        codes = {str(item.get("code")) for item in countries}
        required_origins = {"CN", "IN", "MY", "SG", "TH", "TR", "VN"}
        missing_origins = required_origins - codes
        if not missing_origins:
            passed.append("seven sourcing origins")
        else:
            failed.append(
                "required sourcing origins are missing: "
                + ", ".join(sorted(missing_origins))
            )
    except Exception as exc:  # noqa: BLE001
        failed.append(f"country check failed ({type(exc).__name__})")

    if expect_denied("/api/research/analytics/") and expect_denied("/api/research/export.csv"):
        passed.append("research analytics/export access control")
    else:
        failed.append("research analytics/export must reject anonymous access")

    try:
        status, html = read_text(WEB_BASE)
        if status == 200 and "SourceAI" in html:
            passed.append("Next.js home")
        else:
            failed.append("Next.js home returned unexpected content")
    except Exception as exc:  # noqa: BLE001
        failed.append(f"Next.js home failed ({type(exc).__name__})")

    if sample_slug:
        try:
            status, html = read_text(f"{WEB_BASE}/products/{sample_slug}")
            if status == 200 and sample_slug in html:
                passed.append("product detail")
            else:
                failed.append("product detail returned unexpected content")
        except Exception as exc:  # noqa: BLE001
            failed.append(f"product detail failed ({type(exc).__name__})")

    print("Passed:")
    for item in passed:
        print(f"- {item}")
    if failed:
        print("Failed:")
        for item in failed:
            print(f"- {item}")
        return 1
    print("All read-only smoke checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
