"""Descompresión de EPUB para lectura.

Devuelve los documentos del spine en orden, ya extraídos en disco, de modo que el
visor solo tenga que abrir archivos.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree

from stou.infrastructure.content.inspector import _NS


class EpubExtractor:
    def __init__(self, cache_root: Path | str) -> None:
        self._root = Path(cache_root)
        self._root.mkdir(parents=True, exist_ok=True)

    def unpack(self, path: Path, key: str) -> list[Path]:
        target = self._root / key
        marker = target / ".stou_ok"
        with zipfile.ZipFile(path) as book:
            if not marker.exists():
                target.mkdir(parents=True, exist_ok=True)
                for member in book.namelist():
                    if member.endswith("/") or ".." in member:
                        continue
                    destination = target / member
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with book.open(member) as src, open(destination, "wb") as dst:
                        dst.write(src.read())
                marker.write_text("ok", encoding="utf-8")

        return self._spine(target)

    def _spine(self, root: Path) -> list[Path]:
        container = root / "META-INF" / "container.xml"
        if not container.is_file():
            return sorted(root.rglob("*.xhtml")) or sorted(root.rglob("*.html"))

        tree = ElementTree.fromstring(container.read_text(encoding="utf-8", errors="replace"))
        rootfile = tree.find(".//container:rootfile", _NS)
        opf_rel = rootfile.get("full-path") if rootfile is not None else None
        if not opf_rel:
            return sorted(root.rglob("*.xhtml"))

        opf_path = root / opf_rel
        opf = ElementTree.fromstring(opf_path.read_text(encoding="utf-8", errors="replace"))
        base = opf_path.parent

        manifest = {
            item.get("id"): item.get("href")
            for item in opf.findall(".//opf:manifest/opf:item", _NS)
            if item.get("id") and item.get("href")
        }
        documents: list[Path] = []
        for ref in opf.findall(".//opf:spine/opf:itemref", _NS):
            href = manifest.get(ref.get("idref") or "")
            if not href:
                continue
            candidate = (base / href).resolve()
            if candidate.is_file():
                documents.append(candidate)
        return documents or sorted(root.rglob("*.xhtml"))
