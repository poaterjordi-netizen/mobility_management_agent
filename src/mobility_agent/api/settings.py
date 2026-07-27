from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ApiSettings:
    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: tuple[str, ...] = ()

    @classmethod
    def from_env(cls) -> ApiSettings:
        origins = tuple(
            item.strip()
            for item in os.getenv("MOBILITY_API_CORS_ORIGINS", "").split(",")
            if item.strip()
        )
        return cls(
            environment=os.getenv("MOBILITY_ENV", "development"),
            host=os.getenv("MOBILITY_API_HOST", "127.0.0.1"),
            port=int(os.getenv("MOBILITY_API_PORT", "8000")),
            cors_origins=origins,
        )
