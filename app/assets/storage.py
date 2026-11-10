"""Server-controlled asset paths. Filenames are generated, never taken from user input."""
from __future__ import annotations

import pathlib
import uuid


class AssetStorage:
    def __init__(self, root: str):
        self.root = pathlib.Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, campaign_id: str, data: bytes, ext: str) -> str:
        key = f"{uuid.UUID(campaign_id).hex}/{uuid.uuid4().hex}.{ext}"
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def path(self, key: str) -> pathlib.Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise ValueError("invalid storage key")
        return p

    def delete_campaign(self, campaign_id: str) -> None:
        import shutil
        shutil.rmtree(self.root / uuid.UUID(campaign_id).hex, ignore_errors=True)
