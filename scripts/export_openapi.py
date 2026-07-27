#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from mobility_agent.api.app import create_app
from mobility_agent.api.settings import ApiSettings


def main() -> None:
    output = Path(__file__).resolve().parents[1] / "clients" / "web" / "openapi.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            create_app(ApiSettings(environment="contract-export")).openapi(),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
