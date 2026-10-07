"""Non-secret organization branding; product identity is always preserved."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class Branding:
    product_name: str = "Barcode Buddy"
    organization_name: str | None = None

    @property
    def display_name(self) -> str:
        if self.organization_name:
            return f"{self.organization_name} — {self.product_name}"
        return self.product_name


def load_branding(env: Mapping[str, str] = os.environ) -> Branding:
    organization = env.get("BB_ORGANIZATION_NAME", "").strip()
    return Branding(organization_name=organization or None)
