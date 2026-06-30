from __future__ import annotations

import getpass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"


def _read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_PATH.exists():
        return values
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _write_env(values: dict[str, str]) -> None:
    ordered_keys = [
        "TRISMEGISTUS_HOST",
        "TRISMEGISTUS_PORT",
        "STRIPE_ENABLED",
        "STRIPE_PUBLISHABLE_KEY",
        "STRIPE_SECRET_KEY",
        "STRIPE_ALLOW_LIVE_CHARGES",
    ]
    seen = set()
    lines = [
        "# Local Trismegistus env. Do not commit.",
        "# Stripe sandbox keys are secret-bearing local configuration.",
    ]
    for key in ordered_keys:
        if key in values:
            lines.append(f"{key}={values[key]}")
            seen.add(key)
    for key in sorted(k for k in values if k not in seen):
        lines.append(f"{key}={values[key]}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ENV_PATH.chmod(0o600)


def main() -> None:
    values = _read_env()
    values.setdefault("TRISMEGISTUS_HOST", "127.0.0.1")
    values.setdefault("TRISMEGISTUS_PORT", "8898")
    values["STRIPE_ENABLED"] = "sandbox"
    current_pk = values.get("STRIPE_PUBLISHABLE_KEY", "")
    current_sk = values.get("STRIPE_SECRET_KEY", "")
    pk_prompt = "Stripe publishable test key"
    if current_pk:
        pk_prompt += " [enter to keep existing]"
    pk = input(f"{pk_prompt}: ").strip()
    if pk:
        values["STRIPE_PUBLISHABLE_KEY"] = pk
    elif current_pk:
        values["STRIPE_PUBLISHABLE_KEY"] = current_pk
    else:
        raise SystemExit("Missing STRIPE_PUBLISHABLE_KEY")

    sk_prompt = "Stripe secret test key"
    if current_sk:
        sk_prompt += " [enter to keep existing]"
    sk = getpass.getpass(f"{sk_prompt}: ").strip()
    if sk:
        values["STRIPE_SECRET_KEY"] = sk
    elif current_sk:
        values["STRIPE_SECRET_KEY"] = current_sk
    else:
        raise SystemExit("Missing STRIPE_SECRET_KEY")

    values["STRIPE_ALLOW_LIVE_CHARGES"] = "0"
    _write_env(values)
    print(f"Updated {ENV_PATH}")
    print("Stripe mode: sandbox")
    print("Live charges: disabled")
    print("Restart Trismegistus after setup so /api/status sees the keys.")


if __name__ == "__main__":
    main()
