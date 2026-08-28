"""Identificadores de entidad.

UUIDv7: ordenable por tiempo de creación, lo que sirve para paginar sin ORDER BY
adicional y para reconciliar cambios si más adelante hay sincronización.
"""

from __future__ import annotations

import os
import time
from typing import NewType

EntityId = NewType("EntityId", str)

_last_ms = 0
_counter = 0


def new_id() -> EntityId:
    """Genera un UUIDv7 en texto, monótono dentro del mismo milisegundo."""
    global _last_ms, _counter

    ms = time.time_ns() // 1_000_000
    if ms == _last_ms:
        _counter += 1
    else:
        _last_ms = ms
        _counter = 0

    # 48 bits de timestamp | versión 7 | 12 bits de contador | variante | 62 bits aleatorios
    rand_a = _counter & 0x0FFF
    rand_b = int.from_bytes(os.urandom(8), "big") & 0x3FFF_FFFF_FFFF_FFFF

    value = (ms & 0xFFFF_FFFF_FFFF) << 80
    value |= 0x7 << 76
    value |= rand_a << 64
    value |= 0b10 << 62
    value |= rand_b

    hexed = f"{value:032x}"
    return EntityId(f"{hexed[0:8]}-{hexed[8:12]}-{hexed[12:16]}-{hexed[16:20]}-{hexed[20:32]}")
