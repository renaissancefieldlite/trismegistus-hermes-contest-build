from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trismegistus.integrations import mac_mail  # noqa: E402


def _read_body(args: argparse.Namespace) -> str:
    if args.body_file:
        return Path(args.body_file).read_text(encoding="utf-8")
    return args.body or ""


def main() -> None:
    parser = argparse.ArgumentParser(description="RFL Apple Mail bridge for Trismegistus.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status")

    draft = sub.add_parser("draft")
    draft.add_argument("--to", required=True)
    draft.add_argument("--subject", required=True)
    draft.add_argument("--body", default="")
    draft.add_argument("--body-file")
    draft.add_argument("--reason", default="cli-rfl-mail-draft")
    draft.add_argument("--no-visible-draft", action="store_true")

    send = sub.add_parser("send-approved")
    send.add_argument("--to", required=True)
    send.add_argument("--subject", required=True)
    send.add_argument("--body", default="")
    send.add_argument("--body-file")
    send.add_argument("--reason", default="cli-rfl-mail-send-approved")
    send.add_argument("--approval-phrase", required=True)

    args = parser.parse_args()
    if args.command == "status":
        print(json.dumps(mac_mail.mail_control_status(), indent=2, sort_keys=True))
        return

    if args.command == "draft":
        receipt = mac_mail.create_rfl_mail_action(
            recipient=args.to,
            subject=args.subject,
            body=_read_body(args),
            reason=args.reason,
            create_visible_draft=not args.no_visible_draft,
            send_now=False,
        )
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return

    if args.command == "send-approved":
        receipt = mac_mail.create_rfl_mail_action(
            recipient=args.to,
            subject=args.subject,
            body=_read_body(args),
            reason=args.reason,
            create_visible_draft=True,
            send_now=True,
            approval_phrase=args.approval_phrase,
        )
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return


if __name__ == "__main__":
    main()
