from __future__ import annotations

from pathlib import Path

import yaml

TEMPLATE = Path(__file__).with_name("config.example.yaml")
TARGET = Path(__file__).with_name("config.yaml")


def main() -> None:
    config = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))

    print("PiShock setup wizard (python-pishock)")
    print("This wizard writes middleware/config.yaml for username/api_key/share_code.")
    print("Shock remains disabled by default in policy.allow_shock.")

    username = input("PiShock username: ").strip()
    api_key = input("PiShock API key: ").strip()
    share_code = input("PiShock share code (from PiShock app/site): ").strip()

    if not username or not api_key or not share_code:
        raise SystemExit("username, api_key, and share_code are required")

    config["pishock"]["username"] = username
    config["pishock"]["api_key"] = api_key
    config["pishock"]["share_code"] = share_code

    TARGET.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    print(f"\nCreated {TARGET}.")
    print("Next steps:")
    print("1) Review middleware/config.yaml")
    print("2) Keep allow_shock=false until you're ready")
    print("3) Start service: uvicorn middleware.app:app --reload")


if __name__ == "__main__":
    main()
