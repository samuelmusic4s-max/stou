"""Visores de material: PDF, EPUB, web, YouTube, video, audio, imagen y notas.

Todos exponen la misma interfaz mínima para que el modo estudio los trate igual:
posición actual, salto a una posición y si hay un medio reproduciéndose (dato que
el conteo de tiempo necesita para no pausarse mientras se ve un video).
"""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from stou.application.use_cases.materials import MaterialSource
from stou.domain.values import MaterialKind
from stou.presentation.qt.theme import format_clock

YOUTUBE_ID = re.compile(r"(?:v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{6,})")


class BaseViewer(QWidget):
    """Contrato común de todos los visores."""

    positionChanged = Signal(float)

    def __init__(self, source: MaterialSource, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.source = source

    @property
    def media_playing(self) -> bool:
        return False

    def position(self) -> float:
        return 0.0

    def go_to(self, position: float) -> None:  # noqa: B027 - opcional a propósito
        return

    def shutdown(self) -> None:  # noqa: B027 - opcional a propósito
        return


# --- PDF ----------------------------------------------------------------------


class PdfViewer(BaseViewer):
    def __init__(self, source: MaterialSource, parent: QWidget | None = None) -> None:
        super().__init__(source, parent)
        from PySide6.QtPdf import QPdfDocument
        from PySide6.QtPdfWidgets import QPdfView

        self._document = QPdfDocument(self)
        self._view = QPdfView(self)
        self._view.setDocument(self._document)
        self._view.setPageMode(QPdfView.PageMode.MultiPage)
        self._view.setZoomMode(QPdfView.ZoomMode.FitToWidth)

        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        self._page_box = QSpinBox()
        self._page_box.setMinimum(1)
        self._page_box.setMaximum(1)
        self._page_box.setPrefix("pág. ")
        self._total = QLabel("/ 0")
        self._total.setObjectName("Subtitle")

        prev_btn = QPushButton("◀")
        next_btn = QPushButton("▶")
        prev_btn.setFixedWidth(38)
        next_btn.setFixedWidth(38)
        zoom_in = QPushButton("+")
        zoom_out = QPushButton("−")
        fit = QPushButton("Ajustar")
        zoom_in.setFixedWidth(34)
        zoom_out.setFixedWidth(34)

        for widget in (prev_btn, self._page_box, self._total, next_btn):
            bar.addWidget(widget)
        bar.addStretch(1)
        for widget in (zoom_out, zoom_in, fit):
            bar.addWidget(widget)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(bar)
        layout.addWidget(self._view, 1)

        prev_btn.clicked.connect(lambda: self._jump(self._current_page() - 1))
        next_btn.clicked.connect(lambda: self._jump(self._current_page() + 1))
        self._page_box.editingFinished.connect(
            lambda: self._jump(self._page_box.value() - 1)
        )
        zoom_in.clicked.connect(lambda: self._zoom(1.2))
        zoom_out.clicked.connect(lambda: self._zoom(1 / 1.2))
        fit.clicked.connect(
            lambda: self._view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        )

        self._document.statusChanged.connect(self._on_status)
        navigator = self._view.pageNavigator()
        navigator.currentPageChanged.connect(self._on_page_changed)

        if source.path is not None:
            self._document.load(str(source.path))

    def _on_status(self, status) -> None:  # noqa: ANN001 - enum de Qt
        from PySide6.QtPdf import QPdfDocument

        if status == QPdfDocument.Status.Ready:
            count = self._document.pageCount()
            self._page_box.setMaximum(max(1, count))
            self._total.setText(f"/ {count}")
            start = int(self.source.reading_position or 1)
            if start > 1:
                self._jump(start - 1)

    def _current_page(self) -> int:
        return self._view.pageNavigator().currentPage()

    def _jump(self, page_index: int) -> None:
        from PySide6.QtCore import QPointF

        count = self._document.pageCount()
        if count <= 0:
            return
        target = max(0, min(page_index, count - 1))
        self._view.pageNavigator().jump(target, QPointF(), 0)

    def _zoom(self, factor: float) -> None:
        from PySide6.QtPdfWidgets import QPdfView

        self._view.setZoomMode(QPdfView.ZoomMode.Custom)
        self._view.setZoomFactor(self._view.zoomFactor() * factor)

    @Slot(int)
    def _on_page_changed(self, page: int) -> None:
        self._page_box.blockSignals(True)
        self._page_box.setValue(page + 1)
        self._page_box.blockSignals(False)
        self.positionChanged.emit(float(page + 1))

    def position(self) -> float:
        return float(self._current_page() + 1)

    def go_to(self, position: float) -> None:
        self._jump(int(position) - 1)


# --- Web y YouTube ------------------------------------------------------------

_YOUTUBE_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><style>
html,body{{margin:0;height:100%;background:#000;overflow:hidden}}
#player{{width:100%;height:100%}}
</style></head><body><div id="player"></div>
<script src="https://www.youtube.com/iframe_api"></script>
<script>
var player;
function onYouTubeIframeAPIReady() {{
  player = new YT.Player('player', {{
    videoId: '{video_id}',
    playerVars: {{ start: {start}, rel: 0, modestbranding: 1 }},
    events: {{ onStateChange: function(e) {{
        // El título es el canal por el que la app sabe si hay reproducción.
        document.title = (e.data === 1) ? 'stou:playing' : 'stou:paused';
    }} }}
  }});
}}
setInterval(function() {{
  if (player && player.getCurrentTime) {{
    document.title = (player.getPlayerState() === 1 ? 'stou:playing' : 'stou:paused')
      + ':' + Math.floor(player.getCurrentTime());
  }}
}}, 2000);
</script></body></html>
"""


class WebViewer(BaseViewer):
    """Página web o reproductor embebido de YouTube."""

    def __init__(self, source: MaterialSource, parent: QWidget | None = None) -> None:
        super().__init__(source, parent)
        from PySide6.QtWebEngineWidgets import QWebEngineView

        self._playing = False
        self._seconds = 0.0
        self._view = QWebEngineView(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view, 1)

        if source.kind is MaterialKind.YOUTUBE:
            self._view.titleChanged.connect(self._on_title)
            self._load_youtube(int(source.reading_position or 0))
        elif source.url:
            self._view.setUrl(QUrl(source.url))

    def _load_youtube(self, start: int) -> None:
        video_id = _youtube_id(self.source.url or "")
        if not video_id:
            self._view.setHtml("<p>No se pudo reconocer el video.</p>")
            return
        html = _YOUTUBE_PAGE.format(video_id=video_id, start=max(0, start))
        self._view.setHtml(html, QUrl("https://www.youtube.com/"))

    @Slot(str)
    def _on_title(self, title: str) -> None:
        if not title.startswith("stou:"):
            return
        parts = title.split(":")
        self._playing = len(parts) > 1 and parts[1] == "playing"
        if len(parts) > 2 and parts[2].isdigit():
            self._seconds = float(parts[2])
            self.positionChanged.emit(self._seconds)

    @property
    def media_playing(self) -> bool:
        return self._playing

    def position(self) -> float:
        return self._seconds

    def go_to(self, position: float) -> None:
        if self.source.kind is MaterialKind.YOUTUBE:
            self._load_youtube(int(position))

    def shutdown(self) -> None:
        self._view.setHtml("")


# --- EPUB ---------------------------------------------------------------------


class EpubViewer(BaseViewer):
    def __init__(
        self,
        source: MaterialSource,
        documents: list[Path],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(source, parent)
        from PySide6.QtWebEngineWidgets import QWebEngineView

        self._documents = documents
        self._index = 0
        self._view = QWebEngineView(self)

        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        prev_btn = QPushButton("◀ Anterior")
        next_btn = QPushButton("Siguiente ▶")
        self._label = QLabel()
        self._label.setObjectName("Subtitle")
        bar.addWidget(prev_btn)
        bar.addWidget(next_btn)
        bar.addStretch(1)
        bar.addWidget(self._label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(bar)
        layout.addWidget(self._view, 1)

        prev_btn.clicked.connect(lambda: self._show(self._index - 1))
        next_btn.clicked.connect(lambda: self._show(self._index + 1))

        self._show(int(source.reading_position or 0))

    def _show(self, index: int) -> None:
        if not self._documents:
            self._view.setHtml("<p>El libro no tiene contenido legible.</p>")
            return
        self._index = max(0, min(index, len(self._documents) - 1))
        self._view.setUrl(QUrl.fromLocalFile(str(self._documents[self._index])))
        self._label.setText(f"{self._index + 1} / {len(self._documents)}")
        self.positionChanged.emit(float(self._index))

    def position(self) -> float:
        return float(self._index)

    def go_to(self, position: float) -> None:
        self._show(int(position))


# --- Video y audio ------------------------------------------------------------


class MediaViewer(BaseViewer):
    def __init__(self, source: MaterialSource, parent: QWidget | None = None) -> None:
        super().__init__(source, parent)
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        from PySide6.QtMultimediaWidgets import QVideoWidget

        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)
        self._audio.setVolume(0.8)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        if source.kind is MaterialKind.VIDEO:
            self._video = QVideoWidget(self)
            self._video.setMinimumHeight(240)
            self._player.setVideoOutput(self._video)
            layout.addWidget(self._video, 1)
        else:
            placeholder = QLabel("♪  Audio")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setMinimumHeight(120)
            layout.addWidget(placeholder, 1)

        controls = QHBoxLayout()
        self._play_btn = QPushButton("▶")
        self._play_btn.setFixedWidth(42)
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._time = QLabel("00:00:00 / 00:00:00")
        self._time.setObjectName("Subtitle")
        speed = QPushButton("1×")
        speed.setFixedWidth(46)
        controls.addWidget(self._play_btn)
        controls.addWidget(self._slider, 1)
        controls.addWidget(self._time)
        controls.addWidget(speed)
        layout.addLayout(controls)

        self._play_btn.clicked.connect(self._toggle)
        self._slider.sliderMoved.connect(lambda ms: self._player.setPosition(ms))
        speed.clicked.connect(lambda: self._cycle_speed(speed))
        self._player.positionChanged.connect(self._on_position)
        self._player.durationChanged.connect(self._on_duration)
        self._player.playbackStateChanged.connect(self._on_state)

        if source.path is not None:
            self._player.setSource(QUrl.fromLocalFile(str(source.path)))
            if source.reading_position:
                self._player.setPosition(int(source.reading_position * 1000))

    def _toggle(self) -> None:
        from PySide6.QtMultimedia import QMediaPlayer

        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _cycle_speed(self, button: QPushButton) -> None:
        rates = [1.0, 1.25, 1.5, 1.75, 2.0, 0.75]
        current = self._player.playbackRate()
        nxt = rates[(rates.index(current) + 1) % len(rates)] if current in rates else 1.0
        self._player.setPlaybackRate(nxt)
        button.setText(f"{nxt:g}×")

    @Slot(int)
    def _on_position(self, ms: int) -> None:
        if not self._slider.isSliderDown():
            self._slider.setValue(ms)
        self._time.setText(
            f"{format_clock(ms // 1000)} / {format_clock(self._player.duration() // 1000)}"
        )
        self.positionChanged.emit(ms / 1000)

    @Slot(int)
    def _on_duration(self, ms: int) -> None:
        self._slider.setMaximum(max(0, ms))

    def _on_state(self, _state) -> None:  # noqa: ANN001 - enum de Qt
        from PySide6.QtMultimedia import QMediaPlayer

        playing = self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self._play_btn.setText("⏸" if playing else "▶")

    @property
    def media_playing(self) -> bool:
        from PySide6.QtMultimedia import QMediaPlayer

        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def position(self) -> float:
        return self._player.position() / 1000

    def go_to(self, position: float) -> None:
        self._player.setPosition(int(position * 1000))
        self._player.play()

    def shutdown(self) -> None:
        self._player.stop()


# --- Imagen -------------------------------------------------------------------


class ImageViewer(BaseViewer):
    def __init__(self, source: MaterialSource, parent: QWidget | None = None) -> None:
        super().__init__(source, parent)
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        if source.path is not None:
            self._pixmap = QPixmap(str(source.path))
        else:
            self._pixmap = QPixmap()

        area = QScrollArea()
        area.setWidget(self._label)
        area.setWidgetResizable(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(area, 1)
        self._render()

    def _render(self) -> None:
        if self._pixmap.isNull():
            self._label.setText("No se pudo abrir la imagen.")
            return
        self._label.setPixmap(
            self._pixmap.scaled(
                self._label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def resizeEvent(self, event) -> None:  # noqa: ANN001, N802 - API de Qt
        super().resizeEvent(event)
        self._render()


# --- Nota ---------------------------------------------------------------------


class NoteViewer(BaseViewer):
    """Nota con texto enriquecido. Guarda al perder el foco o al cerrar."""

    saveRequested = Signal(str)

    def __init__(self, source: MaterialSource, parent: QWidget | None = None) -> None:
        super().__init__(source, parent)
        self._editor = QTextEdit()
        self._editor.setAcceptRichText(True)
        self._editor.setHtml(source.body or "")
        self._dirty = False
        self._editor.textChanged.connect(self._mark_dirty)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._editor, 1)

    def _mark_dirty(self) -> None:
        self._dirty = True

    def flush(self) -> None:
        if self._dirty:
            self._dirty = False
            self.saveRequested.emit(self._editor.toHtml())

    def shutdown(self) -> None:
        self.flush()


class UnsupportedViewer(BaseViewer):
    def __init__(self, source: MaterialSource, parent: QWidget | None = None) -> None:
        super().__init__(source, parent)
        label = QLabel(
            f"«{source.title}» no tiene visor propio todavía.\n"
            "Se puede abrir con la aplicación del sistema."
        )
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        open_btn = QPushButton("Abrir con el sistema")
        open_btn.setObjectName("Primary")
        open_btn.clicked.connect(self._open_external)

        layout = QVBoxLayout(self)
        layout.addStretch(1)
        layout.addWidget(label)
        layout.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)

    def _open_external(self) -> None:
        from PySide6.QtGui import QDesktopServices

        target = self.source.path or self.source.url
        if target:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(target))
                if self.source.path
                else QUrl(str(self.source.url))
            )


def _youtube_id(url: str) -> str | None:
    match = YOUTUBE_ID.search(url)
    return match.group(1) if match else None


def build_viewer(
    source: MaterialSource,
    *,
    epub_documents: list[Path] | None = None,
    parent: QWidget | None = None,
) -> BaseViewer:
    """Elige el visor adecuado para el material."""
    if source.kind is MaterialKind.PDF and source.path:
        return PdfViewer(source, parent)
    if source.kind is MaterialKind.EPUB:
        return EpubViewer(source, epub_documents or [], parent)
    if source.kind in (MaterialKind.WEB, MaterialKind.YOUTUBE):
        return WebViewer(source, parent)
    if source.kind in (MaterialKind.VIDEO, MaterialKind.AUDIO) and source.path:
        return MediaViewer(source, parent)
    if source.kind is MaterialKind.IMAGE and source.path:
        return ImageViewer(source, parent)
    if source.kind is MaterialKind.NOTE:
        return NoteViewer(source, parent)
    return UnsupportedViewer(source, parent)
