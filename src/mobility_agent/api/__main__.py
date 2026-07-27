from __future__ import annotations

import uvicorn

from mobility_agent.api.settings import ApiSettings


def main() -> None:
    settings = ApiSettings.from_env()
    uvicorn.run(
        "mobility_agent.api.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
