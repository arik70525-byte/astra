"""Fast local library search."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget,
)

from ui.components import TrackTable
from ui.context import AppContext
from ui.menus import show_track_menu


class SearchPage(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self._tracks: list[dict] = []
        self._build()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(220)
        self._timer.timeout.connect(self._search_local)
        self.query.textChanged.connect(lambda: self._timer.start())
        self.ctx.events.library_changed.connect(self._search_local)
        self.ctx.player.favorite_changed.connect(self._favorite_changed)
        self._search_local()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 28, 34, 30)
        layout.setSpacing(13)
        title = QLabel("Поиск")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Мгновенный поиск по локальной медиатеке: треки, исполнители, альбомы и жанры."
        )
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        row = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setObjectName("Search")
        self.query.setPlaceholderText("Начните вводить название, исполнителя или жанр…")
        self.query.setClearButtonEnabled(True)
        row.addWidget(self.query, 1)
        self.mode = QComboBox()
        self.mode.addItem("Вся медиатека", "all")
        self.mode.addItem("Недавние", "recent")
        self.mode.addItem("Избранное", "liked")
        self.mode.addItem("Демо AURA", "demo")
        self.mode.currentIndexChanged.connect(self._search_local)
        row.addWidget(self.mode)
        layout.addLayout(row)

        self.local_count = QLabel("")
        self.local_count.setObjectName("Muted")
        layout.addWidget(self.local_count)
        self.local_table = TrackTable()
        self.local_table.play_requested.connect(self.ctx.player.play_track)
        self.local_table.favorite_requested.connect(self.ctx.player.toggle_favorite)
        self.local_table.menu_requested.connect(self._menu)
        layout.addWidget(self.local_table, 1)

    def _search_local(self):
        query = self.query.text().strip()
        mode = str(self.mode.currentData() or "all")
        if mode == "liked":
            tracks = self.ctx.db.favorite_tracks(limit=500)
            if query:
                needle = query.casefold()
                tracks = [
                    track for track in tracks
                    if needle in " ".join(
                        str(track.get(key) or "") for key in
                        ("title", "artist", "album", "genre")
                    ).casefold()
                ]
        elif mode == "recent":
            tracks = self.ctx.db.recent_tracks(120)
            if query:
                needle = query.casefold()
                tracks = [
                    track for track in tracks
                    if needle in " ".join(
                        str(track.get(key) or "") for key in
                        ("title", "artist", "album", "genre")
                    ).casefold()
                ]
        elif mode == "demo":
            tracks = [
                track for track in self.ctx.db.search_tracks(query, limit=500)
                if "AURA Originals" in str(track.get("album") or "")
                or str(track.get("artist") or "") == "AURA Studio"
            ]
        elif query:
            tracks = self.ctx.db.search_tracks(query, limit=500)
        else:
            tracks = self.ctx.db.recent_tracks(100)
        self._tracks = tracks
        self.local_table.set_tracks(tracks)
        if query:
            self.local_count.setText(f"Найдено: {len(tracks)} · запрос «{query}»")
        else:
            self.local_count.setText(f"Треков: {len(tracks)}")

    def _favorite_changed(self, *_args):
        self._search_local()

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._search_local()
            return
        super().keyPressEvent(event)

    def _menu(self, track: dict, point):
        show_track_menu(self, track, self.ctx.db, self.ctx.player, on_changed=self._search_local)
