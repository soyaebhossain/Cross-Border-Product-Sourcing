from __future__ import annotations

import argparse
import json
import time

from app.config import get_settings
from app.db import SessionLocal
from app.services.notifications import dispatch_outbox_batch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dispatch queued SourceAI email/SMS/WhatsApp notifications."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process one batch and exit (suitable for a scheduler or Kubernetes CronJob).",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=10,
        help="Polling interval for continuous worker mode (default: 10).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Override CATALOG_NOTIFICATION_DISPATCH_BATCH_SIZE.",
    )
    return parser.parse_args()


def dispatch_once(batch_size: int | None) -> dict[str, int]:
    settings = get_settings()
    with SessionLocal() as session:
        return dispatch_outbox_batch(
            session,
            settings=settings,
            limit=batch_size,
        )


def main() -> int:
    args = parse_args()
    if args.poll_seconds < 1:
        raise SystemExit("--poll-seconds must be at least 1")
    while True:
        result = dispatch_once(args.batch_size)
        # Only counts are emitted. Destinations, provider URLs, tokens, message
        # bodies, and transport exception strings are intentionally excluded.
        print(json.dumps({"event": "notification_dispatch", **result}), flush=True)
        if args.once:
            return 0
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
