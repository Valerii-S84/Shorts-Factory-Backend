from __future__ import annotations

from hashlib import sha256
from pathlib import Path


class LocalStorage:
    def write_bytes(self, path: Path, content: bytes) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return self.checksum(path)

    def checksum(self, path: Path) -> str:
        digest = sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
