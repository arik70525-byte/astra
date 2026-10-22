"""Home / discovery page."""
from __future__ import annotations

import random
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from core.ai import PROVIDER_LABELS
from ui.components import (
    AuraOrb, MediaCard, SectionHeader, StatChip, TrackTable, clear_layout,
    format_hours, horizontal_cards,
)
from ui.context import AppContext
from ui.menus import show_track_menu


class HomePage(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self._tracks: list[dict] = []
        self._build()
        ctx.events.library_changed.connect(self.refresh)
        ctx.player.favorite_changed.connect(self._favorite_changed)
        self.refresh()

    def _build(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer = QWidget()
        self.layout_main = QVBoxLayout(outer)
        self.layout_main.setContentsMargins(34, 28, 34, 36)
        self.layout_main.setSpacing(22)
        scroll.setWidget(outer)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        header = QHBoxLayout()
        header.setSpacing(12)
        head_text = QVBoxLayout()
        self.greeting = QLabel("Добрый вечер")
        self.greeting.setObjectName("PageTitle")
        self.subtitle = QLabel("Локальная музыка, ИИ-агенты и исследования — в одном окне.")
        self.subtitle.setObjectName("Muted")
        head_text.addWidget(self.greeting)
        head_text.addWidget(self.subtitle)
        header.addLayout(head_text)
        header.addStretch(1)
        provider = str(self.ctx.settings.get("ai.provider", "ollama"))
        model = self.ctx.settings.get("ai.model", "")
        self.ai_status = QLabel(f"●  {PROVIDER_LABELS.get(provider, provider)} · {model or 'модель не выбрана'}")
        self.ai_status.setObjectName("Muted")
        self.ai_status.setStyleSheet(
            "background:#15161b; border:1px solid #2a2c35; border-radius:15px; "
            "padding:7px 13px; color:#b9bbc5;"
        )
        header.addWidget(self.ai_status)
        self.layout_main.addLayout(header)

        hero = QFrame()
        hero.setObjectName("Hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(30, 26, 30, 26)
        hero_layout.setSpacing(20)
        hero_left = QVBoxLayout()
        hero_left.setSpacing(9)
        kicker = QLabel("AURA WAVE")
        kicker.setObjectName("Accent")
        kicker.setStyleSheet("letter-spacing:4px; font-size:11px; font-weight:700;")
        title = QLabel("Музыка, которая\nподстраивается под тебя")
        title.setObjectName("HeroTitle")
        text = QLabel("Локальная медиатека, умные подборки и ИИ, который знает твои треки.")
        text.setObjectName("HeroText")
        text.setWordWrap(True)
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.wave_btn = QPushButton("▶  Включить волну")
        self.wave_btn.setObjectName("Accent")
        self.wave_btn.clicked.connect(self._play_wave)
        ai_btn = QPushButton("✦  Спросить ИИ")
        ai_btn.setObjectName("")
        ai_btn.clicked.connect(lambda: self.ctx.events.open_chat.emit("assistant"))
        buttons.addWidget(self.wave_btn)
        buttons.addWidget(ai_btn)
        buttons.addStretch(1)
        hero_left.addWidget(kicker)
        hero_left.addWidget(title)
        hero_left.addWidget(text)
        hero_left.addSpacing(8)
        hero_left.addLayout(buttons)
        hero_layout.addLayout(hero_left, 3)
        self.orb = AuraOrb()
        self.orb.setMinimumWidth(260)
        self.ctx.player.state_changed.connect(
            lambda state: self.orb.set_level(0.85 if state == "playing" else 0.18)
        )
        hero_layout.addWidget(self.orb, 1)
        self.layout_main.addWidget(hero)

        stats = QHBoxLayout()
        stats.setSpacing(10)
        self.track_chip = StatChip("0", "треков")
        self.album_chip = StatChip("0", "альбомов")
        self.artist_chip = StatChip("0", "исполнителей")
        self.hours_chip = StatChip("0 ч", "музыки")
        for chip in (self.track_chip, self.album_chip, self.artist_chip, self.hours_chip):
            stats.addWidget(chip)
        stats.addStretch(1)
        self.layout_main.addLayout(stats)

        self.recent_header = SectionHeader("Недавно добавленные")
        self.layout_main.addWidget(self.recent_header)
        self.recent_container = QWidget()
        self.recent_layout = QHBoxLayout(self.recent_container)
        self.recent_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_layout.setSpacing(10)
        recent_scroll = QScrollArea()
        recent_scroll.setWidgetResizable(True)
        recent_scroll.setFrameShape(QFrame.Shape.NoFrame)
        recent_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        recent_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        recent_scroll.setFixedHeight(248)
        recent_scroll.setWidget(self.recent_container)
        self.layout_main.addWidget(recent_scroll)

        self.empty_hint = QLabel("Медиатека пока пуста. Откройте «Коллекция» и добавьте папку с музыкой.")
        self.empty_hint.setObjectName("Muted")
        self.empty_hint.setVisible(False)
        self.layout_main.addWidget(self.empty_hint)

        self.fav_header = SectionHeader("Любимые треки")
        self.layout_main.addWidget(self.fav_header)
        self.fav_table = TrackTable()
        self.fav_table.setMinimumHeight(250)
        self.fav_table.play_requested.connect(self._play_track)
        self.fav_table.favorite_requested.connect(self.ctx.player.toggle_favorite)
        self.fav_table.menu_requested.connect(self._track_menu)
        self.layout_main.addWidget(self.fav_table)
        self.layout_main.addStretch(1)

    def refresh(self):
        hour = datetime.now().hour
        greeting = "Доброе утро" if 5 <= hour < 12 else "Добрый день" if 12 <= hour < 18 else "Добрый вечер"
        self.greeting.setText(greeting)
        stats = self.ctx.db.stats()
        self.track_chip.set_value(str(stats["tracks"]))
        self.album_chip.set_value(str(stats["albums"]))
        self.artist_chip.set_value(str(stats["artists"]))
        self.hours_chip.set_value(format_hours(stats["seconds"]))
        provider = str(self.ctx.settings.get("ai.provider", "ollama"))
        model = str(self.ctx.settings.get("ai.model", ""))
        self.ai_status.setText(f"●  {PROVIDER_LABELS.get(provider, provider)} · {model or 'модель не выбрана'}")
        self._tracks = self.ctx.db.recent_tracks(12)
        clear_layout(self.recent_layout)
        if self._tracks:
            for track in self._tracks[:8]:
                card = MediaCard(
                    title=track.get("title") or "",
                    subtitle=track.get("artist") or "",
                    cover=track.get("cover_path"),
                    data=track,
                )
                card.clicked.connect(self._play_track)
                self.recent_layout.addWidget(card)
            self.recent_layout.addStretch(1)
            self.empty_hint.setVisible(False)
        else:
            self.recent_layout.addStretch(1)
            self.empty_hint.setVisible(True)
        favs = self.ctx.db.favorite_tracks(limit=8)
        self.fav_table.set_tracks(favs)
        self.fav_table.setVisible(bool(favs))
        self.fav_header.setVisible(bool(favs))
        self.wave_btn.setEnabled(bool(stats["tracks"]))

    def _play_track(self, track: dict):
        if track:
            self.ctx.player.play_track(track)

    def _play_wave(self):
        tracks = self.ctx.db.tracks(limit=700, order="title")
        if not tracks:
            self.ctx.events.toast.emit("В медиатеке нет треков. Сначала просканируйте папку.")
            return
        random.shuffle(tracks)
        self.ctx.player.play_wave(tracks[:300])

    def _favorite_changed(self, track_id: int, value: bool):
        self.fav_table.update_favorite(track_id, value)
        if not value:
            self.refresh()

    def _track_menu(self, track: dict, point):
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.addAction("▶  Играть", lambda: self.ctx.player.play_track(track))
        menu.addAction("В очередь", lambda: self.ctx.player.add_to_queue(track))
        menu.addAction("♡  Любимое", lambda: self.ctx.player.toggle_favorite(track))
        menu.exec(point)
