from pathlib import Path

TEMPLATE = Path(__file__).with_name("config.example.yaml")
TARGET = Path(__file__).with_name("config.yaml")


def main() -> None:
    if TARGET.exists():
        print("config.yaml already exists")
        return
    TARGET.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    print("Created middleware/config.yaml. Edit credentials and secret before running.")


if __name__ == "__main__":
    main()
