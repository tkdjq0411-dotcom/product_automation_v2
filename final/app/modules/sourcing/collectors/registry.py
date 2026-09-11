from __future__ import annotations
from urllib.parse import urlparse
from typing import Any

from .naver import collect_naver

async def collect_product(url: str) -> dict[str, Any]:
    host=(urlparse(url).hostname or '').lower()
    if host.endswith('naver.com'):
        return await collect_naver(url)
    # Existing platform importer remains available while collectors are migrated one-by-one.
    from app.modules.sourcing.url_importer import import_product_url
    return await import_product_url(url)
