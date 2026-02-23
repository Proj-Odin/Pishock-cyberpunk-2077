from __future__ import annotations

from pathlib import Path

import httpx
import yaml

TEMPLATE = Path(__file__).with_name("config.example.yaml")
TARGET = Path(__file__).with_name("config.yaml")


def _pick_index(max_index: int, prompt: str) -> int:
    while True:
        raw = input(prompt).strip()
        try:
            value = int(raw)
        except ValueError:
            print("Please enter a number.")
            continue
        if 1 <= value <= max_index:
            return value - 1
        print(f"Please enter a number between 1 and {max_index}.")


def main() -> None:
    config = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))

    print("PiShock setup wizard (new discovery flow)")
    print("- We'll resolve UserID and your target shocker using API key + username.")
    print("- Then we'll write middleware/config.yaml for you.")

    username = input("PiShock username: ").strip()
    api_key = input("PiShock API key: ").strip()

    if not username or not api_key:
        raise SystemExit("username and api_key are required")

    with httpx.Client(timeout=10.0) as client:
        auth_resp = client.get(
            "https://auth.pishock.com/Auth/GetUserIfAPIKeyValid",
            params={"apikey": api_key, "username": username},
        )
        auth_resp.raise_for_status()
        auth_data = auth_resp.json()
        user_id = auth_data.get("UserID") or auth_data.get("userID") or auth_data.get("userid")
        if not user_id:
            raise SystemExit("Could not resolve UserID from API key + username")

        shares_resp = client.get(
            "https://ps.pishock.com/PiShock/GetShareCodesByOwner",
            params={"UserId": user_id, "Token": api_key, "api": "true"},
        )
        shares_resp.raise_for_status()
        share_data = shares_resp.json()

        share_ids: list[int] = []
        for owner, ids in (share_data.items() if isinstance(share_data, dict) else []):
            if not isinstance(ids, list):
                continue
            for sid in ids:
                try:
                    share_id = int(sid)
                except (TypeError, ValueError):
                    continue
                share_ids.append(share_id)
                print(f"Found shareId {share_id} from owner '{owner}'")

        if not share_ids:
            raise SystemExit("No share IDs found. Ensure your API key has access to at least one share.")

        selected_share_id = share_ids[0]
        if len(share_ids) > 1:
            print("\nSelect share ID:")
            for idx, sid in enumerate(share_ids, start=1):
                print(f"  {idx}. {sid}")
            selected_share_id = share_ids[_pick_index(len(share_ids), "Choice: ")]

        shockers_resp = client.get(
            "https://ps.pishock.com/PiShock/GetShockersByShareIds",
            params=[
                ("UserId", str(user_id)),
                ("Token", api_key),
                ("api", "true"),
                ("shareIds", str(selected_share_id)),
            ],
        )
        shockers_resp.raise_for_status()
        shockers_data = shockers_resp.json()

        candidates: list[dict] = []
        if isinstance(shockers_data, dict):
            for _, shockers in shockers_data.items():
                if isinstance(shockers, list):
                    candidates.extend(item for item in shockers if isinstance(item, dict))

        if not candidates:
            raise SystemExit("No shockers were returned for the selected share ID")

        print("\nSelect target shocker:")
        for idx, candidate in enumerate(candidates, start=1):
            print(
                f"  {idx}. {candidate.get('shockerName', 'Unknown')} "
                f"(shareCode={candidate.get('shareCode', 'n/a')})"
            )

        chosen = candidates[_pick_index(len(candidates), "Choice: ")]

    config["pishock"]["username"] = username
    config["pishock"]["api_key"] = api_key
    config["pishock"]["user_id"] = int(user_id)
    config["pishock"]["share_id"] = int(chosen.get("shareId") or selected_share_id)
    config["pishock"]["share_code"] = str(chosen.get("shareCode") or "")
    config["pishock"]["target_shocker_name"] = str(chosen.get("shockerName") or "")

    TARGET.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    print(f"\nCreated {TARGET} with resolved PiShock settings.")
    print("Review the file and update safety policy (allow_shock, max intensity, mappings) before use.")


if __name__ == "__main__":
    main()
