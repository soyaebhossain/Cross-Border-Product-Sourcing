from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.config import get_settings  # noqa: E402
from app.services.notifications import DeliveryError, email_adapter_for  # noqa: E402


def _validated_recipient(value: str) -> str:
    recipient = value.strip()
    if not recipient or "@" not in recipient or "\r" in recipient or "\n" in recipient:
        raise ValueError("A valid test recipient email is required")
    return recipient


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Send one SourceAI provider-verification email using runtime secrets.",
    )
    parser.add_argument(
        "--to",
        dest="recipient",
        help="Test recipient. Omit to enter it interactively.",
    )
    args = parser.parse_args()
    settings = get_settings()
    if not settings.password_reset_email_configured:
        print("Email provider is not configured. Add Resend or SMTP runtime secrets first.", file=sys.stderr)
        return 2

    try:
        recipient = _validated_recipient(args.recipient or input("Test recipient email: "))
        receipt = email_adapter_for(settings).send(
            SimpleNamespace(
                id=f"provider-check-{uuid4().hex}",
                destination=recipient,
                payload={
                    "title": "SourceAI email delivery check",
                    "body": (
                        "Your SourceAI transactional email provider is configured correctly.\n\n"
                        "No account or password change was made."
                    ),
                },
            )
        )
    except (DeliveryError, ValueError) as exc:
        # DeliveryError deliberately contains only provider-neutral safe text.
        print(f"Email delivery check failed: {exc}", file=sys.stderr)
        return 1

    suffix = f" Provider message: {receipt.provider_message_id}." if receipt.provider_message_id else ""
    print(f"Email delivery check accepted.{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
