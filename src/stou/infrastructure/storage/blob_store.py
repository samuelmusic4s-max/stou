"""Almacén de archivos por hash de contenido.

La biblioteca deja de depender de dónde estaba el archivo original, y dos
importaciones del mismo libro no ocupan el disco dos veces.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path

from stou.application.ports.content import StoredBlob

CHUNK = 1024 * 1024


class BlobStore:
    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def store(self, source: Path) -> StoredBlob:
        source = Path(source)
        if not source.is_file():
            raise FileNotFoundError(f"No existe el archivo {source}")

        ext = source.suffix.lower().lstrip(".")
        digest = hashlib.sha256()
        size = 0

        # Se copia a un temporal en el mismo volumen y se renombra: si algo falla
        # a medio camino no queda un blob truncado en la biblioteca.
        fd, tmp_name = tempfile.mkstemp(dir=self._root, suffix=".part")
        tmp_path = Path(tmp_name)
        try:
            with open(source, "rb") as src, os.fdopen(fd, "wb") as dst:
                while chunk := src.read(CHUNK):
                    digest.update(chunk)
                    dst.write(chunk)
                    size += len(chunk)
            blob_hash = digest.hexdigest()
            target = self.path_for(blob_hash, ext)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                tmp_path.unlink(missing_ok=True)
            else:
                shutil.move(str(tmp_path), str(target))
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise

        return StoredBlob(hash=blob_hash, ext=ext, size_bytes=size)

    def path_for(self, blob_hash: str, ext: str) -> Path:
        suffix = f".{ext}" if ext else ""
        return self._root / blob_hash[:2] / f"{blob_hash}{suffix}"

    def exists(self, blob_hash: str, ext: str) -> bool:
        return self.path_for(blob_hash, ext).is_file()

    def delete(self, blob_hash: str, ext: str) -> None:
        path = self.path_for(blob_hash, ext)
        path.unlink(missing_ok=True)
        parent = path.parent
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()

    def total_bytes(self) -> int:
        return sum(f.stat().st_size for f in self._root.rglob("*") if f.is_file())
