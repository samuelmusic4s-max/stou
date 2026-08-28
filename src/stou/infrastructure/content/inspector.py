"""Inspección de archivos: tipo, metadatos y estructura interna.

Aquí vive todo lo que sabe leer formatos. El resto del sistema solo ve
``InspectedMaterial``.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from stou.application.ports.content import InspectedMaterial, OutlineEntry
from stou.domain.values import MaterialKind

log = logging.getLogger(__name__)

EXTENSIONS: dict[str, MaterialKind] = {
    "pdf": MaterialKind.PDF,
    "epub": MaterialKind.EPUB,
    "png": MaterialKind.IMAGE,
    "jpg": MaterialKind.IMAGE,
    "jpeg": MaterialKind.IMAGE,
    "gif": MaterialKind.IMAGE,
    "bmp": MaterialKind.IMAGE,
    "webp": MaterialKind.IMAGE,
    "svg": MaterialKind.IMAGE,
    "mp4": MaterialKind.VIDEO,
    "mkv": MaterialKind.VIDEO,
    "webm": MaterialKind.VIDEO,
    "avi": MaterialKind.VIDEO,
    "mov": MaterialKind.VIDEO,
    "mp3": MaterialKind.AUDIO,
    "m4a": MaterialKind.AUDIO,
    "wav": MaterialKind.AUDIO,
    "ogg": MaterialKind.AUDIO,
    "flac": MaterialKind.AUDIO,
    "opus": MaterialKind.AUDIO,
    "md": MaterialKind.NOTE,
    "txt": MaterialKind.NOTE,
}


class FileInspector:
    def detect_kind(self, path: Path) -> MaterialKind:
        ext = Path(path).suffix.lower().lstrip(".")
        return EXTENSIONS.get(ext, MaterialKind.OTHER)

    def inspect(self, path: Path, kind: MaterialKind) -> InspectedMaterial:
        path = Path(path)
        try:
            if kind is MaterialKind.PDF:
                return _inspect_pdf(path)
            if kind is MaterialKind.EPUB:
                return _inspect_epub(path)
            if kind in (MaterialKind.VIDEO, MaterialKind.AUDIO):
                return _inspect_media(path, kind)
        except Exception:
            log.warning("No se pudo inspeccionar %s", path.name, exc_info=True)
        return InspectedMaterial(kind=kind, title=path.stem)


# --- PDF ----------------------------------------------------------------------


def _inspect_pdf(path: Path) -> InspectedMaterial:
    from pypdf import PdfReader

    reader = PdfReader(str(path), strict=False)
    page_count = len(reader.pages)
    title = None
    try:
        meta = reader.metadata
        if meta and meta.title:
            title = str(meta.title).strip() or None
    except Exception:
        title = None

    entries: list[OutlineEntry] = []
    try:
        entries = _pdf_outline(reader)
    except Exception:
        log.debug("PDF sin índice aprovechable: %s", path.name)

    return InspectedMaterial(
        kind=MaterialKind.PDF,
        title=title or path.stem,
        page_count=page_count,
        outline=tuple(entries),
    )


def _pdf_outline(reader) -> list[OutlineEntry]:  # noqa: ANN001 - tipo de pypdf
    entries: list[OutlineEntry] = []

    def walk(items, level: int) -> None:
        for item in items:
            if isinstance(item, list):
                walk(item, level + 1)
                continue
            try:
                title = str(item.title).strip()
                page_index = reader.get_destination_page_number(item)
            except Exception:
                continue
            if title:
                entries.append(
                    OutlineEntry(title=title, start=float(page_index + 1), level=level)
                )

    walk(reader.outline, 0)
    # Solo el primer nivel se vuelve sección: los subcapítulos harían secciones
    # demasiado pequeñas para asignar a una tarea.
    top = [e for e in entries if e.level == 0]
    return top or entries


# --- EPUB ---------------------------------------------------------------------

_NS = {
    "container": "urn:oasis:names:tc:opendocument:xmlns:container",
    "opf": "http://www.idpf.org/2007/opf",
    "ncx": "http://www.daisy.org/z3986/2005/ncx/",
    "xhtml": "http://www.w3.org/1999/xhtml",
}


def _inspect_epub(path: Path) -> InspectedMaterial:
    with zipfile.ZipFile(path) as book:
        container = ElementTree.fromstring(book.read("META-INF/container.xml"))
        rootfile = container.find(".//container:rootfile", _NS)
        opf_path = rootfile.get("full-path") if rootfile is not None else None
        if not opf_path:
            return InspectedMaterial(kind=MaterialKind.EPUB, title=path.stem)

        opf = ElementTree.fromstring(book.read(opf_path))
        base = opf_path.rsplit("/", 1)[0] if "/" in opf_path else ""

        title_el = opf.find(".//{http://purl.org/dc/elements/1.1/}title")
        title = (title_el.text or "").strip() if title_el is not None else ""

        manifest: dict[str, str] = {}
        for item in opf.findall(".//opf:manifest/opf:item", _NS):
            item_id = item.get("id")
            href = item.get("href")
            if item_id and href:
                manifest[item_id] = href

        spine: list[str] = []
        for ref in opf.findall(".//opf:spine/opf:itemref", _NS):
            idref = ref.get("idref")
            if idref and idref in manifest:
                spine.append(manifest[idref])

        outline = _epub_outline(book, opf, manifest, base, spine)
        if not outline:
            outline = [
                OutlineEntry(title=f"Capítulo {i + 1}", start=float(i)) for i in range(len(spine))
            ]

        return InspectedMaterial(
            kind=MaterialKind.EPUB,
            title=title or path.stem,
            page_count=len(spine) or None,
            outline=tuple(outline),
        )


def _epub_outline(
    book: zipfile.ZipFile,
    opf: ElementTree.Element,
    manifest: dict[str, str],
    base: str,
    spine: list[str],
) -> list[OutlineEntry]:
    """Lee el índice del EPUB y lo traduce a posiciones del spine."""
    spine_index = {href.split("#")[0]: i for i, href in enumerate(spine)}

    def resolve(href: str) -> float | None:
        clean = href.split("#")[0]
        candidates = [clean, f"{base}/{clean}" if base else clean]
        for candidate in candidates:
            normalized = candidate.removeprefix(f"{base}/") if base else candidate
            if normalized in spine_index:
                return float(spine_index[normalized])
        return None

    entries: list[OutlineEntry] = []

    # EPUB 3: documento de navegación.
    nav_href = next(
        (
            item.get("href")
            for item in opf.findall(".//opf:manifest/opf:item", _NS)
            if (item.get("properties") or "").find("nav") >= 0
        ),
        None,
    )
    if nav_href:
        full = f"{base}/{nav_href}" if base else nav_href
        try:
            nav = ElementTree.fromstring(book.read(full))
            for anchor in nav.iter():
                if not anchor.tag.endswith("a"):
                    continue
                href = anchor.get("href")
                text = "".join(anchor.itertext()).strip()
                if href and text:
                    start = resolve(href)
                    if start is not None:
                        entries.append(OutlineEntry(title=text, start=start))
        except Exception:
            entries = []

    # EPUB 2: toc.ncx.
    if not entries:
        ncx_href = next(
            (href for item_id, href in manifest.items() if href.lower().endswith(".ncx")),
            None,
        )
        if ncx_href:
            full = f"{base}/{ncx_href}" if base else ncx_href
            try:
                ncx = ElementTree.fromstring(book.read(full))
                for point in ncx.findall(".//ncx:navPoint", _NS):
                    label = point.find("./ncx:navLabel/ncx:text", _NS)
                    content = point.find("./ncx:content", _NS)
                    if label is None or content is None:
                        continue
                    text = (label.text or "").strip()
                    href = content.get("src") or ""
                    start = resolve(href)
                    if text and start is not None:
                        entries.append(OutlineEntry(title=text, start=start))
            except Exception:
                entries = []

    # Una entrada por posición: varias entradas del índice pueden caer en el mismo
    # archivo del spine y no queremos secciones vacías.
    unique: dict[float, OutlineEntry] = {}
    for entry in entries:
        unique.setdefault(entry.start, entry)
    return [unique[key] for key in sorted(unique)]


# --- Medios -------------------------------------------------------------------


def _inspect_media(path: Path, kind: MaterialKind) -> InspectedMaterial:
    duration = _probe_duration(path)
    return InspectedMaterial(kind=kind, title=path.stem, duration_seconds=duration)


def _probe_duration(path: Path) -> float | None:
    """Duración vía ffprobe si está instalado. Sin él, el visor la completa al abrir."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        out = subprocess.run(  # noqa: S603 - ruta resuelta por shutil.which
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if out.returncode != 0:
            return None
        value = json.loads(out.stdout).get("format", {}).get("duration")
        return float(value) if value else None
    except Exception:
        return None
