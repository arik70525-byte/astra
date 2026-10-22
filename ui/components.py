"""Reusable dark-theme UI components."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap, QRadialGradient,
)
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)


def format_duration(seconds: float) -> str:
    try:
        seconds = max(0, int(float(seconds)))
    except Exception:
        seconds = 0
    if seconds >= 3600:
        return f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"
    return f"{seconds // 60}:{seconds % 60:02d}"


def format_hours(seconds: float) -> str:
    hours = float(seconds or 0) / 3600
    if hours >= 100:
        return f"{hours:.0f} ч"
    return f"{hours:.1f} ч"


def elide(text: str, limit: int = 36) -> str:
    text = str(text or "")
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


class CoverWidget(QWidget):
    """Rounded cover with a deterministic gradient placeholder."""

    def __init__(self, size: int = 56, radius: int = 10, parent: QWidget | None = None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._seed = "AURA"
        self._initials = "A"
        self._size = size
        self._radius = radius
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_cover(self, path: str | None, title: str = "", size: int | None = None):
        self._seed = title or Path(str(path or "AURA")).stem
        self._initials = "".join(
            word[0] for word in self._seed.replace("_", " ").split()[:2]
        ).upper() or "A"
        self._pixmap = None
        if path:
            candidate = Path(str(path))
            if candidate.exists():
                pix = QPixmap(str(candidate))
                if not pix.isNull():
                    self._pixmap = pix
        if size:
            self._size = size
            self._radius = max(6, int(size * 0.12))
            self.setFixedSize(size, size)
        self.update()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)
        painter.setClipPath(path)
        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            digest = hashlib.sha1(self._seed.encode("utf-8", "ignore")).digest()
            hue = int.from_bytes(digest[:2], "big") % 360
            c1 = QColor.fromHsl(hue, 90, 180, 255)
            c2 = QColor.fromHsl((hue + 48) % 360, 110, 60, 255)
            gradient = QLinearGradient(0, 0, self.width(), self.height())
            gradient.setColorAt(0, c1)
            gradient.setColorAt(1, c2)
            painter.fillRect(rect, gradient)
            painter.setPen(QColor(255, 255, 255, 52))
            painter.setFont(QFont("Segoe UI", max(12, int(self.width() * 0.28)), QFont.Weight.Bold))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._initials)
            painter.setPen(Qt.PenStyle.NoPen)
        painter.setClipping(False)
        painter.setPen(QPen(QColor(255, 255, 255, 22), 1))
        painter.drawPath(path)


class TrackTable(QTableWidget):
    play_requested = Signal(object)
    favorite_requested = Signal(object)
    menu_requested = Signal(object, object)

    HEADERS = ["#", "ТРЕК", "ИСПОЛНИТЕЛЬ", "АЛЬБОМ", "ВРЕМЯ", ""]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(0, len(self.HEADERS), parent)
        self.tracks: list[dict[str, Any]] = []
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setWordWrap(False)
        self.setSortingEnabled(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)
        self.cellDoubleClicked.connect(self._double_click)
        self.cellClicked.connect(self._click)
        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, header.ResizeMode.Fixed)
        header.setSectionResizeMode(1, header.ResizeMode.Stretch)
        header.setSectionResizeMode(2, header.ResizeMode.Stretch)
        header.setSectionResizeMode(3, header.ResizeMode.Stretch)
        header.setSectionResizeMode(4, header.ResizeMode.Fixed)
        header.setSectionResizeMode(5, header.ResizeMode.Fixed)
        self.setColumnWidth(0, 42)
        self.setColumnWidth(4, 68)
        self.setColumnWidth(5, 44)
        self.verticalHeader().setDefaultSectionSize(45)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_tracks(self, tracks: list[dict[str, Any]]):
        self.setUpdatesEnabled(False)
        self.clearContents()
        self.tracks = list(tracks or [])
        self.setRowCount(len(self.tracks))
        accent = QColor("#ffd54a")
        muted = QColor("#8f929f")
        for row, track in enumerate(self.tracks):
            values = [
                str(row + 1),
                str(track.get("title") or ""),
                str(track.get("artist") or ""),
                str(track.get("album") or "—"),
                format_duration(track.get("duration") or 0),
                "♥" if track.get("favorite") else "♡",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, track)
                if col in (0, 4, 5):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 0:
                    item.setForeground(muted)
                if col == 5:
                    item.setForeground(accent if track.get("favorite") else muted)
                    item.setToolTip("В любимые / убрать")
                if col == 1:
                    item.setToolTip(str(track.get("path") or track.get("external_url") or ""))
                self.setItem(row, col, item)
        self.setUpdatesEnabled(True)
        self.viewport().update()

    def update_favorite(self, track_id: int, value: bool):
        for track in self.tracks:
            if int(track.get("id", -1)) == int(track_id):
                track["favorite"] = value
        for row in range(self.rowCount()):
            item = self.item(row, 5)
            track = item.data(Qt.ItemDataRole.UserRole) if item else None
            if track and int(track.get("id", -1)) == int(track_id):
                item.setText("♥" if value else "♡")
                item.setForeground(QColor("#ffd54a" if value else "#8f929f"))
                item.setData(Qt.ItemDataRole.UserRole, {**track, "favorite": value})
                for col in range(self.columnCount()):
                    cell = self.item(row, col)
                    if cell:
                        data = cell.data(Qt.ItemDataRole.UserRole)
                        if data:
                            cell.setData(Qt.ItemDataRole.UserRole, {**data, "favorite": value})
                break

    def _track_for_cell(self, row: int) -> dict[str, Any] | None:
        item = self.item(row, 1)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _double_click(self, row: int, column: int):
        track = self._track_for_cell(row)
        if track:
            self.play_requested.emit(track)

    def _click(self, row: int, column: int):
        if column == 5:
            track = self._track_for_cell(row)
            if track:
                self.favorite_requested.emit(track)

    def _show_menu(self, point: QPoint):
        row = self.rowAt(point.y())
        track = self._track_for_cell(row) if row >= 0 else None
        if track:
            self.menu_requested.emit(track, self.viewport().mapToGlobal(point))


class MediaCard(QWidget):
    clicked = Signal(object)

    def __init__(self, title: str = "", subtitle: str = "", cover: str | None = None,
                 data: dict | None = None, size: int = 164, parent: QWidget | None = None):
        super().__init__(parent)
        self._data = data or {}
        self._hover = False
        self._size = size
        self.setFixedWidth(size + 16)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        self.cover = CoverWidget(size, 14)
        self.cover.set_cover(cover, title)
        layout.addWidget(self.cover, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.title_label = QLabel(elide(title, 22))
        self.title_label.setStyleSheet("font-weight: 650; font-size: 13px;")
        self.title_label.setToolTip(title)
        self.subtitle_label = QLabel(elide(subtitle, 24))
        self.subtitle_label.setObjectName("Muted")
        self.subtitle_label.setStyleSheet("font-size: 11px;")
        self.subtitle_label.setToolTip(subtitle)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)
        layout.addStretch(1)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def set_data(self, title: str, subtitle: str, cover: str | None, data: dict | None):
        self._data = data or {}
        self.title_label.setText(elide(title, 22))
        self.title_label.setToolTip(title)
        self.subtitle_label.setText(elide(subtitle, 24))
        self.subtitle_label.setToolTip(subtitle)
        self.cover.set_cover(cover, title)

    def enterEvent(self, event):  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self._data)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):  # noqa: N802
        if self._hover:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 12))
            painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 14, 14)


class SectionHeader(QWidget):
    def __init__(self, title: str, action_text: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        label = QLabel(title)
        label.setObjectName("SectionTitle")
        layout.addWidget(label)
        layout.addStretch(1)
        self.action = QPushButton(action_text)
        self.action.setObjectName("Ghost")
        self.action.setVisible(bool(action_text))
        layout.addWidget(self.action)


class StatChip(QFrame):
    def __init__(self, value: str, label: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("SoftCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("font-size: 20px; font-weight: 750;")
        self.label = QLabel(label)
        self.label.setObjectName("Tiny")
        layout.addWidget(self.value_label)
        layout.addWidget(self.label)

    def set_value(self, value: str):
        self.value_label.setText(value)


class Pill(QPushButton):
    def __init__(self, text: str, checkable: bool = False, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName("Chip")
        self.setCheckable(checkable)


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


def horizontal_cards(items: list[dict[str, Any]], on_click, parent: QWidget | None = None) -> QWidget:
    container = QWidget(parent)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    for item in items:
        card = MediaCard(
            title=str(item.get("title") or item.get("name") or ""),
            subtitle=str(item.get("subtitle") or item.get("artist") or ""),
            cover=item.get("cover_path"),
            data=item,
        )
        card.clicked.connect(on_click)
        layout.addWidget(card)
    layout.addStretch(1)
    return container


class AuraOrb(QWidget):
    """Animated accent orb + equalizer used by the home hero.

    The widget is intentionally self-contained and uses the live accent from
    ``ui.theme`` so switching palettes immediately changes the animation.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._phase = 0.0
        self._level = 0.18
        self.setMinimumSize(230, 220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._timer = QTimer(self)
        self._timer.setInterval(38)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self):
        self._phase = (self._phase + 0.045) % (math.pi * 2)
        self.update()

    def set_level(self, value: float):
        self._level = max(0.08, min(1.0, float(value)))
        self.update()

    def paintEvent(self, event):  # noqa: N802
        from ui import theme

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        width = max(1, self.width())
        height = max(1, self.height())
        cx = width * 0.5
        cy = height * 0.45
        radius = min(width, height) * 0.29
        accent = QColor(theme.ACCENT)
        glow = QColor(theme.accent_colors(theme_choice()).get("glow", theme.ACCENT))

        for index, factor in enumerate((1.75, 1.35, 1.02)):
            radial = QRadialGradient(cx, cy, radius * factor)
            color = QColor(accent if index < 2 else glow)
            color.setAlpha(34 - index * 7)
            radial.setColorAt(0.0, color)
            color2 = QColor(color)
            color2.setAlpha(0)
            radial.setColorAt(1.0, color2)
            painter.setBrush(radial)
            painter.setPen(Qt.PenStyle.NoPen)
            wobble = math.sin(self._phase + index) * 8
            painter.drawEllipse(
                QRectF(cx - radius * factor - wobble, cy - radius * factor,
                       radius * factor * 2 + wobble * 2, radius * factor * 2)
            )

        painter.setBrush(Qt.BrushStyle.NoBrush)
        for ring in range(3):
            pen = QPen(QColor(accent.red(), accent.green(), accent.blue(), 145 - ring * 32), 1.4)
            painter.setPen(pen)
            rr = radius * (0.78 + 0.18 * ring)
            painter.drawEllipse(QRectF(cx - rr, cy - rr, rr * 2, rr * 2))

        # Rotating orbit dot.
        angle = self._phase * 1.15
        orbit = radius * 1.12
        dot_x = cx + math.cos(angle) * orbit
        dot_y = cy + math.sin(angle) * orbit
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        painter.drawEllipse(QRectF(dot_x - 5, dot_y - 5, 10, 10))

        # Equalizer bars.
        bars = 17
        gap = 5.0
        bar_width = max(3.0, (width * 0.62 - gap * (bars - 1)) / bars)
        baseline = height - 20
        start_x = (width - (bar_width * bars + gap * (bars - 1))) * 0.5
        for index in range(bars):
            wave = (math.sin(self._phase * 2.1 + index * 0.7) + 1) * 0.5
            wave2 = (math.sin(self._phase * 1.3 + index * 1.7) + 1) * 0.5
            bar_h = 8 + (height * 0.16) * (self._level * wave + 0.22 * wave2)
            color = QColor(accent)
            color.setAlpha(105 + int(120 * wave))
            painter.setBrush(color)
            x = start_x + index * (bar_width + gap)
            painter.drawRoundedRect(
                QRectF(x, baseline - bar_h, bar_width, bar_h), bar_width / 2, bar_width / 2
            )
        painter.end()


def theme_choice() -> str:
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    return str(app.property("auraAccent") or "sunset") if app else "sunset"
