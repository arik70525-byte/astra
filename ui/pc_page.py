"""Visible PC-control page built on the existing approved tool registry."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from core.i18n import tr
from ui.context import AppContext


class PcPage(QWidget):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 28, 34, 26)
        layout.setSpacing(12)
        header = QHBoxLayout()
        title = QLabel(tr(self.ctx.settings, "pc.title"))
        title.setObjectName("PageTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.access = QLabel("")
        self.access.setObjectName("Tiny")
        header.addWidget(self.access)
        layout.addLayout(header)
        subtitle = QLabel(tr(self.ctx.settings, "pc.subtitle"))
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        columns = QHBoxLayout()
        columns.setSpacing(12)
        columns.addWidget(self._overview_card(), 1)
        columns.addWidget(self._capture_card(), 1)
        columns.addWidget(self._media_card(), 1)
        layout.addLayout(columns)

        power = QFrame()
        power.setObjectName("Card")
        p = QHBoxLayout(power)
        p.setContentsMargins(14, 10, 14, 10)
        p.addWidget(QLabel(tr(self.ctx.settings, "pc.power")))
        self.power_combo = QComboBox()
        for key, text_key in (
            ("lock", "pc.power_lock"),
            ("sleep", "pc.power_sleep"),
            ("cancel_shutdown", "pc.power_cancel"),
            ("restart", "pc.power_restart"),
            ("shutdown", "pc.power_shutdown"),
        ):
            self.power_combo.addItem(tr(self.ctx.settings, text_key), key)
        p.addWidget(self.power_combo, 1)
        run_power = QPushButton(tr(self.ctx.settings, "pc.run"))
        run_power.setObjectName("Ghost")
        run_power.clicked.connect(self._power)
        p.addWidget(run_power)
        layout.addWidget(power)

        open_row = QFrame()
        open_row.setObjectName("Card")
        o = QHBoxLayout(open_row)
        o.setContentsMargins(14, 10, 14, 10)
        o.addWidget(QLabel(tr(self.ctx.settings, "pc.open")))
        self.open_edit = QLineEdit()
        self.open_edit.setPlaceholderText(tr(self.ctx.settings, "pc.open_placeholder"))
        o.addWidget(self.open_edit, 1)
        open_btn = QPushButton(tr(self.ctx.settings, "pc.open"))
        open_btn.setObjectName("Ghost")
        open_btn.clicked.connect(self._open_target)
        o.addWidget(open_btn)
        layout.addWidget(open_row)

        self.output = QPlainTextEdit()
        self.output.setObjectName("TerminalView")
        self.output.setReadOnly(True)
        self.output.setPlaceholderText(tr(self.ctx.settings, "pc.output") + "…")
        layout.addWidget(self.output, 1)
        self._refresh_access()

    def _card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("Card")
        box = QVBoxLayout(card)
        box.setContentsMargins(15, 13, 15, 13)
        box.setSpacing(7)
        label = QLabel(title)
        label.setStyleSheet("font-weight:700; font-size:12px;")
        box.addWidget(label)
        return card, box

    def _overview_card(self) -> QFrame:
        card, box = self._card(tr(self.ctx.settings, "pc.overview"))
        for text, name, args in (
            (tr(self.ctx.settings, "pc.info"), "system_info", {}),
            (tr(self.ctx.settings, "pc.window"), "active_window", {}),
            (tr(self.ctx.settings, "pc.processes"), "list_processes", {"limit": 30}),
        ):
            button = QPushButton(text)
            button.setObjectName("Ghost")
            button.clicked.connect(lambda _=False, n=name, a=args: self._run(n, a))
            box.addWidget(button)
        box.addStretch(1)
        return card

    def _capture_card(self) -> QFrame:
        card, box = self._card(tr(self.ctx.settings, "pc.capture"))
        screen = QPushButton("⌁  " + tr(self.ctx.settings, "pc.screenshot"))
        screen.setObjectName("Ghost")
        screen.clicked.connect(lambda: self._run("screenshot", {"label": "pc-page"}))
        read = QPushButton(tr(self.ctx.settings, "pc.clipboard"))
        read.setObjectName("Ghost")
        read.clicked.connect(lambda: self._run("clipboard_get", {}))
        write = QPushButton(tr(self.ctx.settings, "pc.clipboard_set"))
        write.setObjectName("Ghost")
        write.clicked.connect(self._write_clipboard)
        for button in (screen, read, write):
            box.addWidget(button)
        box.addStretch(1)
        return card

    def _media_card(self) -> QFrame:
        card, box = self._card(tr(self.ctx.settings, "pc.media_windows"))
        grid = QGridLayout()
        grid.setSpacing(6)
        media = [
            ("⏮", "previous"), ("⏯", "play_pause"), ("⏭", "next"),
            ("−", "volume_down"), ("✕", "mute"), ("+", "volume_up"),
        ]
        for index, (label, action) in enumerate(media):
            button = QPushButton(label)
            button.setObjectName("Ghost")
            button.setToolTip(action)
            button.clicked.connect(lambda _=False, a=action: self._run("media_key", {"action": a}))
            grid.addWidget(button, index // 3, index % 3)
        box.addLayout(grid)
        for text_key, action in (
            ("pc.minimize", "minimize"),
            ("pc.maximize", "maximize"),
            ("pc.close_window", "close"),
        ):
            button = QPushButton(tr(self.ctx.settings, text_key))
            button.setObjectName("Ghost")
            button.clicked.connect(lambda _=False, a=action: self._run("window_control", {"action": a}))
            box.addWidget(button)
        box.addStretch(1)
        return card

    def _approve(self, title: str, details: str) -> bool:
        box = QMessageBox(self)
        box.setWindowTitle(tr(self.ctx.settings, "pc.approval_title"))
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(title)
        box.setInformativeText(tr(self.ctx.settings, "pc.approval_hint"))
        box.setDetailedText(details)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        box.button(QMessageBox.StandardButton.Yes).setText(tr(self.ctx.settings, "pc.allow"))
        box.button(QMessageBox.StandardButton.No).setText(tr(self.ctx.settings, "pc.deny"))
        return box.exec() == QMessageBox.StandardButton.Yes

    def _run(self, name: str, args: dict):
        self.output.setPlainText(tr(self.ctx.settings, "pc.executing"))
        try:
            result = self.ctx.tools.execute(name, args, self._approve)
        except Exception as exc:
            result = f"ОШИБКА: {exc}"
        self.output.setPlainText(str(result or tr(self.ctx.settings, "pc.no_result")))
        self._refresh_access()

    def _write_clipboard(self):
        text, ok = QInputDialog.getMultiLineText(
            self, tr(self.ctx.settings, "pc.clipboard_set"),
            tr(self.ctx.settings, "pc.clipboard_prompt"),
        )
        if ok:
            self._run("clipboard_set", {"text": text})

    def _power(self):
        action = str(self.power_combo.currentData() or "lock")
        if action in {"restart", "shutdown", "sleep"}:
            answer = QMessageBox.question(
                self, tr(self.ctx.settings, "pc.power"),
                tr(self.ctx.settings, "pc.confirm_power"),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._run("system_power", {"action": action})

    def _open_target(self):
        target = self.open_edit.text().strip()
        if target:
            self._run("open_in_shell", {"target": target})

    def _refresh_access(self):
        allowed = bool(self.ctx.tools.policy.allow_system)
        self.access.setText(
            tr(self.ctx.settings, "pc.system_allowed" if allowed else "pc.system_disabled")
        )
        self.access.setStyleSheet(
            "font-size:10px; color:#5bdd9a;" if allowed else "font-size:10px; color:#c9a55a;"
        )

    def showEvent(self, event):  # noqa: N802
        self._refresh_access()
        super().showEvent(event)
