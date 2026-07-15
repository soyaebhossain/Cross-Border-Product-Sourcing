from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


API_BASE = os.getenv("REBUILD_API_BASE", "http://127.0.0.1:8001")
WEB_BASE = os.getenv("REBUILD_WEB_BASE", "http://127.0.0.1:3001")


def read_json(url: str, *, method: str = "GET", body: dict | None = None) -> tuple[int, object]:
    payload = None
    headers: dict[str, str] = {}
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=payload, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def read_text(url: str) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=15) as response:
        return response.status, response.read().decode("utf-8", "ignore")


def main() -> int:
    checks: list[str] = []
    failures: list[str] = []

    try:
        status, health = read_json(f"{API_BASE}/api/health")
        if status == 200 and health.get("status") == "ok":
            checks.append("api health ok")
        else:
            failures.append("api health returned unexpected payload")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"api health failed: {exc}")

    try:
        status, products = read_json(f"{API_BASE}/api/products/")
        if status == 200 and isinstance(products, list) and products:
            checks.append(f"api products ok ({len(products)} items)")
            sample_slug = products[0]["slug"]
        else:
            sample_slug = None
            failures.append("api products returned empty payload")
    except Exception as exc:  # noqa: BLE001
        sample_slug = None
        failures.append(f"api products failed: {exc}")

    try:
        status, countries = read_json(f"{API_BASE}/api/countries/")
        if status == 200 and isinstance(countries, list) and countries:
            checks.append(f"api countries ok ({len(countries)} items)")
        else:
            failures.append("api countries returned empty payload")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"api countries failed: {exc}")

    try:
        status, recommendation = read_json(
            f"{API_BASE}/api/recommendations/cheapest-country/",
            method="POST",
            body={
                "product_slug": "iphone-14",
                "qty": 1,
                "delivery_type": "DOOR",
                "priority": "balanced",
            },
        )
        if status == 200 and recommendation.get("recommendations"):
            checks.append("api recommendation ok")
        else:
            failures.append("api recommendation returned empty payload")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"api recommendation failed: {exc}")

    try:
        status, html = read_text(WEB_BASE)
        if status == 200 and "Cross-border sourcing rebuilt with FastAPI and Next.js." in html:
            checks.append("web home ok")
        else:
            failures.append("web home returned unexpected content")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"web home failed: {exc}")

    if sample_slug:
        try:
            status, html = read_text(f"{WEB_BASE}/products/{sample_slug}")
            if status == 200 and "Hybrid sourcing recommendation" in html:
                checks.append("web product detail ok")
            else:
                failures.append("web product detail returned unexpected content")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"web product detail failed: {exc}")

    print("Checks:")
    for item in checks:
        print(f"- {item}")

    if failures:
        print("Failures:")
        for item in failures:
            print(f"- {item}")
        return 1

    print("All rebuild smoke checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
