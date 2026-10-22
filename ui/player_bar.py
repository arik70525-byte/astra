"""Bottom player bar."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from ui.components import CoverWidget, format_duration
from ui.context import AppContext


class PlayerBar(QFrame):
    queue_requested = Signal()

    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.player = ctx.player
        self._duration = 0
        self._dragging = False
        self.setObjectName("PlayerBar")
        self.setFixedHeight(92)
        self._build()
        self._connect()
        self._set_state("stopped")

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(16)
        left = QHBoxLayout()
        left.setSpacing(10)
        self.cover = CoverWidget(56, 8)
        left.addWidget(self.cover)
        info = QVBoxLayout()
        info.setSpacing(2)
        self.title = QLabel("Ничего не играет")
        self.title.setStyleSheet("font-weight:650; font-size:13px;")
        self.artist = QLabel("Выберите трек в медиатеке")
        self.artist.setObjectName("Muted")
        self.artist.setStyleSheet("font-size:11px;")
        info.addWidget(self.title)
        info.addWidget(self.artist)
        left.addLayout(info)
        self.like = QPushButton("♡")
        self.like.setObjectName("Icon")
        self.like.setFixedSize(34, 34)
        self.like.setToolTip("В любимые")
        self.like.clicked.connect(self._toggle_favorite)
        left.addWidget(self.like)
        layout.addLayout(left, 3)

        center = QVBoxLayout()
        center.setSpacing(2)
        controls = QHBoxLayout()
        controls.setSpacing(4)
        controls.addStretch(1)
        self.shuffle = QPushButton("⇄")
        self.shuffle.setObjectName("Icon")
        self.shuffle.setCheckable(True)
        self.shuffle.setFixedSize(32, 32)
        self.shuffle.setToolTip("Перемешать")
        self.shuffle.clicked.connect(self._shuffle)
        self.prev = QPushButton("|◀")
        self.prev.setObjectName("Icon")
        self.prev.setFixedSize(34, 34)
        self.prev.clicked.connect(self.player.previous)
        self.play = QPushButton("▶")
        self.play.setObjectName("Play")
        self.play.setFixedSize(44, 44)
        self.play.clicked.connect(self._play_pause)
        self.next = QPushButton("▶|")
        self.next.setObjectName("Icon")
        self.next.setFixedSize(34, 34)
        self.next.clicked.connect(self.player.next)
        self.repeat = QPushButton("↻")
        self.repeat.setObjectName("Icon")
        self.repeat.setFixedSize(32, 32)
        self.repeat.setToolTip("Повтор выключен")
        self.repeat.clicked.connect(self._repeat)
        icon_font = QFont("Segoe UI Symbol", 15)
        for button in (self.shuffle, self.repeat):
            button.setFont(icon_font)
        for button in (self.shuffle, self.prev, self.play, self.next, self.repeat):
            controls.addWidget(button)
        controls.addStretch(1)
        center.addLayout(controls)
        progress = QHBoxLayout()
        progress.setSpacing(8)
        self.elapsed = QLabel("0:00")
        self.elapsed.setObjectName("Tiny")
        self.elapsed.setFixedWidth(38)
        self.elapsed.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1)
        self.slider.sliderPressed.connect(self._slider_pressed)
        self.slider.sliderReleased.connect(self._slider_released)
        self.slider.sliderMoved.connect(self._slider_moved)
        self.total = QLabel("0:00")
        self.total.setObjectName("Tiny")
        self.total.setFixedWidth(38)
        progress.addWidget(self.elapsed)
        progress.addWidget(self.slider, 1)
        progress.addWidget(self.total)
        center.addLayout(progress)
        layout.addLayout(center, 5)

        right = QHBoxLayout()
        right.setSpacing(8)
        self.queue_btn = QPushButton("≡  Очередь")
        self.queue_btn.setObjectName("Ghost")
        self.queue_btn.clicked.connect(self.queue_requested.emit)
        right.addWidget(self.queue_btn)
        right.addStretch(1)
        vol_icon = QLabel("VOL")
        vol_icon.setStyleSheet("font-size:9px; font-weight:700; color:#9295a3;")
        right.addWidget(vol_icon)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setFixedWidth(110)
        self.volume.setValue(int(self.ctx.settings.get("ui.volume", 72)))
        self.volume.valueChanged.connect(self._volume_changed)
        self.volume.sliderReleased.connect(self._volume_saved)
        right.addWidget(self.volume)
        layout.addLayout(right, 2)

    def _connect(self):
        self.player.current_changed.connect(self._current_changed)
        self.player.state_changed.connect(self._set_state)
        self.player.position_changed.connect(self._position)
        self.player.favorite_changed.connect(self._favorite_changed)
        self.player.queue_changed.connect(self._queue_changed)
        self.player.error.connect(self.ctx.events.toast.emit)
        self.player.external_requested.connect(self._external)
        self.shuffle.setChecked(bool(self.ctx.settings.get("ui.shuffle", False)))
        self.player.set_shuffle(self.shuffle.isChecked())
        repeat = str(self.ctx.settings.get("ui.repeat", "off"))
        self.player.set_repeat(repeat)
        self._repeat_label()

    def _current_changed(self, track: dict):
        self.cover.set_cover(track.get("cover_path"), track.get("title") or "")
        self.title.setText(str(track.get("title") or "Без названия"))
        self.title.setToolTip(str(track.get("title") or ""))
        self.artist.setText(str(track.get("artist") or "Неизвестный исполнитель"))
        self.artist.setToolTip(str(track.get("artist") or ""))
        self._duration = int(float(track.get("duration") or 0) * 1000)
        self.slider.setRange(0, max(1, self._duration))
        self.slider.setValue(0)
        self.elapsed.setText("0:00")
        self.total.setText(format_duration(self._duration / 1000))
        self._favorite_changed(int(track.get("id", -1)), bool(track.get("favorite")))
        if not track.get("is_local"):
            self.play.setEnabled(False)
        else:
            self.play.setEnabled(True)

    def _set_state(self, state: str):
        self.play.setText("⏸" if state == "playing" else "▶")
        self.play.setToolTip("Пауза" if state == "playing" else "Играть")

    def _position(self, position: int, duration: int):
        if duration and duration != self._duration:
            self._duration = duration
            self.slider.setRange(0, max(1, duration))
            self.total.setText(format_duration(duration / 1000))
        if not self._dragging:
            self.slider.blockSignals(True)
            self.slider.setValue(max(0, min(position, self.slider.maximum())))
            self.slider.blockSignals(False)
            self.elapsed.setText(format_duration(position / 1000))

    def _slider_pressed(self):
        self._dragging = True

    def _slider_moved(self, value: int):
        self.elapsed.setText(format_duration(value / 1000))

    def _slider_released(self):
        self._dragging = False
        self.player.seek(int(self.slider.value()))
        self.elapsed.setText(format_duration(self.slider.value() / 1000))

    def _play_pause(self):
        if self.player.current is None:
            tracks = self.ctx.db.tracks(limit=250, order="added")
            if tracks:
                self.player.play_tracks(tracks, 0)
            return
        if self.player.current.get("is_local") is False:
            self._external(self.player.current)
            return
        self.player.toggle()

    def _toggle_favorite(self):
        self.player.toggle_favorite()

    def _favorite_changed(self, track_id: int, value: bool):
        current = self.player.current
        if current and int(current.get("id", -1)) == int(track_id):
            self.like.setText("♥" if value else "♡")
            self.like.setStyleSheet("color:#ffd54a;" if value else "color:#9295a3;")
            self.like.setToolTip("Убрать из любимых" if value else "В любимые")

    def _queue_changed(self, queue: list):
        self.queue_btn.setText(f"≡  Очередь {len(queue)}")

    def _shuffle(self):
        self.player.set_shuffle(self.shuffle.isChecked())
        self.ctx.settings.set("ui.shuffle", self.shuffle.isChecked())
        self.ctx.settings.save()

    def _repeat(self):
        order = ["off", "all", "one"]
        current = self.player.repeat
        new = order[(order.index(current) + 1) % len(order)]
        self.player.set_repeat(new)
        self.ctx.settings.set("ui.repeat", new)
        self.ctx.settings.save()
        self._repeat_label()

    def _repeat_label(self):
        value = self.player.repeat
        self.repeat.setText("↻¹" if value == "one" else "↻")
        self.repeat.setStyleSheet("color:#ffd54a;" if value != "off" else "")
        self.repeat.setToolTip(
            "Повтор выключен" if value == "off" else "Повтор всей очереди" if value == "all" else "Повтор трека"
        )

    def _volume_changed(self, value: int):
        self.player.set_volume(value)

    def _volume_saved(self):
        self.ctx.settings.set("ui.volume", int(self.volume.value()))
        self.ctx.settings.save()

    def _external(self, track: dict):
        url = str(track.get("external_url") or "")
        if not url:
            self.ctx.events.toast.emit("У внешнего трека нет ссылки.")
            return
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl(url))
        self.ctx.events.toast.emit("Внешняя ссылка открыта в браузере.")
