"""Persistencia: migraciones, transacciones y almacén de archivos."""

from __future__ import annotations

from pathlib import Path

import pytest

from stou.composition.container import Container
from stou.domain.entities.category import Category
from stou.infrastructure.persistence.database import Database
from stou.infrastructure.storage.blob_store import BlobStore
from stou.shared.clock import FixedClock


def test_las_migraciones_se_aplican_una_sola_vez(tmp_path: Path) -> None:
    db = Database(tmp_path / "stou.db")
    assert db.version == 1
    assert db.migrate() == 0  # nada nuevo por aplicar
    db.close()


def test_la_transaccion_se_revierte_si_nadie_hace_commit(
    container: Container, clock: FixedClock
) -> None:
    with container.uow as uow:
        uow.categories.add(Category.create(name="Se descarta", now=clock.now()))
        # sin commit

    with container.uow as uow:
        assert uow.categories.list_all() == []


def test_la_transaccion_se_revierte_ante_una_excepcion(
    container: Container, clock: FixedClock
) -> None:
    with pytest.raises(RuntimeError), container.uow as uow:
        uow.categories.add(Category.create(name="Tampoco", now=clock.now()))
        raise RuntimeError("algo falló antes del commit")

    with container.uow as uow:
        assert uow.categories.list_all() == []


def test_el_commit_persiste(container: Container, clock: FixedClock) -> None:
    with container.uow as uow:
        uow.categories.add(Category.create(name="Queda", now=clock.now()))
        uow.commit()

    with container.uow as uow:
        assert [c.name for c in uow.categories.list_all()] == ["Queda"]


def test_las_fechas_vuelven_en_utc(container: Container, clock: FixedClock) -> None:
    with container.uow as uow:
        original = Category.create(name="Fechas", now=clock.now())
        uow.categories.add(original)
        uow.commit()
        recovered = uow.categories.get(original.id)

    assert recovered is not None
    assert recovered.created_at == clock.now()
    assert recovered.created_at.tzinfo is not None


def test_el_blob_store_deduplica_por_contenido(tmp_path: Path) -> None:
    store = BlobStore(tmp_path / "library")
    first = tmp_path / "a.txt"
    second = tmp_path / "b.txt"
    first.write_text("mismo contenido", encoding="utf-8")
    second.write_text("mismo contenido", encoding="utf-8")

    blob_a = store.store(first)
    blob_b = store.store(second)

    assert blob_a.hash == blob_b.hash
    assert store.exists(blob_a.hash, blob_a.ext)
    assert len([p for p in (tmp_path / "library").rglob("*") if p.is_file()]) == 1


def test_el_material_sobrevive_a_que_borren_el_original(
    use_cases: dict, tmp_path: Path
) -> None:
    original = tmp_path / "apunte.txt"
    original.write_text("contenido", encoding="utf-8")

    material_id = use_cases["import_files"].execute(paths=[original]).imported[0]
    original.unlink()

    source = use_cases["resolve_source"].execute(material_id=material_id)
    assert source.path is not None
    assert source.path.is_file()


def test_no_deja_archivos_a_medias_si_falla_la_copia(tmp_path: Path) -> None:
    store = BlobStore(tmp_path / "library")
    with pytest.raises(FileNotFoundError):
        store.store(tmp_path / "no_existe.pdf")
    assert list((tmp_path / "library").rglob("*.part")) == []
