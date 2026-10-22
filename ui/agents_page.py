"""Agents, skills and plugins management page."""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from core.config import DATA_DIR
from ui.context import AppContext


class AgentsPage(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self._build()
        self.refresh()
        ctx.events.settings_changed.connect(self.refresh)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.inner = QWidget()
        self.layout = QVBoxLayout(self.inner)
        self.layout.setContentsMargins(34, 28, 34, 36)
        self.layout.setSpacing(16)
        scroll.setWidget(self.inner)
        root.addWidget(scroll)
        header = QHBoxLayout()
        title = QLabel("Агенты и навыки")
        title.setObjectName("PageTitle")
        header.addWidget(title)
        header.addStretch(1)
        reload_btn = QPushButton("↻  Обновить")
        reload_btn.clicked.connect(self.reload_all)
        open_btn = QPushButton("Открыть папку")
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(DATA_DIR))))
        header.addWidget(reload_btn)
        header.addWidget(open_btn)
        self.layout.addLayout(header)
        note = QLabel(
            "Агенты задают роль и набор инструментов. Навыки — это markdown-инструкции, "
            "которые подключаются к системному промпту. Плагины выполняют локальный Python-код "
            "и загружаются только после включения."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        self.layout.addWidget(note)

        self.agents_title = QLabel("Агенты")
        self.agents_title.setObjectName("SectionTitle")
        self.layout.addWidget(self.agents_title)
        self.agents_container = QWidget()
        self.agents_layout = QVBoxLayout(self.agents_container)
        self.agents_layout.setContentsMargins(0, 0, 0, 0)
        self.agents_layout.setSpacing(10)
        self.layout.addWidget(self.agents_container)

        self.skills_title = QLabel("Навыки")
        self.skills_title.setObjectName("SectionTitle")
        self.layout.addWidget(self.skills_title)
        self.skills_container = QWidget()
        self.skills_layout = QVBoxLayout(self.skills_container)
        self.skills_layout.setContentsMargins(0, 0, 0, 0)
        self.skills_layout.setSpacing(8)
        self.layout.addWidget(self.skills_container)

        self.plugins_title = QLabel("Плагины")
        self.plugins_title.setObjectName("SectionTitle")
        self.layout.addWidget(self.plugins_title)
        self.plugins_container = QWidget()
        self.plugins_layout = QVBoxLayout(self.plugins_container)
        self.plugins_layout.setContentsMargins(0, 0, 0, 0)
        self.plugins_layout.setSpacing(8)
        self.layout.addWidget(self.plugins_container)
        self.layout.addStretch(1)

    def _clear(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def refresh(self):
        self._clear(self.agents_layout)
        for agent in self.ctx.agents.agents:
            card = QFrame()
            card.setObjectName("SoftCard")
            h = QHBoxLayout(card)
            h.setContentsMargins(16, 13, 16, 13)
            icon = QLabel(agent.icon)
            icon.setFixedWidth(38)
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon.setStyleSheet("font-size:24px; color:#ffd54a;")
            h.addWidget(icon)
            text = QVBoxLayout()
            name = QLabel(agent.name)
            name.setStyleSheet("font-weight:650; font-size:14px;")
            desc = QLabel(agent.description or "Без описания")
            desc.setObjectName("Muted")
            desc.setWordWrap(True)
            tools = QLabel(
                "инструменты: " + (", ".join(agent.tools) if agent.tools and "*" not in agent.tools else "все доступные")
            )
            tools.setObjectName("Tiny")
            text.addWidget(name)
            text.addWidget(desc)
            text.addWidget(tools)
            h.addLayout(text, 1)
            chat_btn = QPushButton("Открыть чат")
            chat_btn.clicked.connect(lambda _=False, aid=agent.id: self.ctx.events.open_chat.emit(aid))
            h.addWidget(chat_btn)
            self.agents_layout.addWidget(card)

        self._clear(self.skills_layout)
        enabled = set(self.ctx.settings.get("ai.enabled_skills", []) or [])
        for skill in self.ctx.agents.skills:
            row = QFrame()
            row.setObjectName("SoftCard")
            h = QHBoxLayout(row)
            h.setContentsMargins(14, 10, 14, 10)
            box = QCheckBox(skill.name)
            box.setChecked(skill.id in enabled)
            box.stateChanged.connect(
                lambda state, sid=skill.id: self._toggle_skill(sid, state == Qt.CheckState.Checked.value)
            )
            h.addWidget(box, 1)
            desc = QLabel(skill.description)
            desc.setObjectName("Tiny")
            desc.setWordWrap(True)
            h.addWidget(desc, 2)
            self.skills_layout.addWidget(row)

        self._clear(self.plugins_layout)
        self.ctx.plugins.reload()
        for plugin in self.ctx.plugins.discover():
            row = QFrame()
            row.setObjectName("SoftCard")
            h = QHBoxLayout(row)
            h.setContentsMargins(14, 10, 14, 10)
            box = QCheckBox(plugin["name"])
            box.setChecked(bool(plugin["enabled"]))
            box.stateChanged.connect(
                lambda state, pid=plugin["id"]: self._toggle_plugin(pid, state == Qt.CheckState.Checked.value)
            )
            h.addWidget(box, 1)
            text = QLabel(plugin.get("description") or "")
            text.setObjectName("Tiny")
            text.setWordWrap(True)
            h.addWidget(text, 2)
            if plugin.get("error"):
                err = QLabel("Ошибка: " + str(plugin["error"])[:180])
                err.setObjectName("Danger")
                h.addWidget(err, 2)
            self.plugins_layout.addWidget(row)
        if not self.ctx.agents.skills:
            self.skills_layout.addWidget(QLabel("Навыки не найдены."))
        if not self.ctx.plugins.discover():
            self.plugins_layout.addWidget(QLabel("Плагины не найдены."))

        access = (
            f"Доступ ИИ: {'запись разрешена' if self.ctx.tools.policy.allow_write else 'только чтение'}, "
            f"терминал {'включён' if self.ctx.tools.policy.allow_shell else 'выключен'}, "
            f"сеть {'включена' if self.ctx.tools.policy.allow_network else 'выключена'}. "
            f"Папки: {self.ctx.tools.policy.describe()}"
        )
        if hasattr(self, "access_label"):
            self.access_label.setText(access)
        else:
            self.access_label = QLabel(access)
            self.access_label.setObjectName("Banner")
            self.access_label.setWordWrap(True)
            self.layout.addWidget(self.access_label)

    def _toggle_skill(self, skill_id: str, enabled: bool):
        values = set(self.ctx.settings.get("ai.enabled_skills", []) or [])
        if enabled:
            values.add(skill_id)
        else:
            values.discard(skill_id)
        self.ctx.settings.set("ai.enabled_skills", sorted(values))
        self.ctx.settings.save()
        self.ctx.events.settings_changed.emit()
        self.ctx.events.toast.emit("Навыки обновлены.")

    def _toggle_plugin(self, plugin_id: str, enabled: bool):
        values = set(self.ctx.settings.get("ai.enabled_plugins", []) or [])
        if enabled:
            values.add(plugin_id)
        else:
            values.discard(plugin_id)
        self.ctx.settings.set("ai.enabled_plugins", sorted(values))
        self.ctx.settings.save()
        self.ctx.tools.refresh()
        self.ctx.events.settings_changed.emit()
        self.ctx.events.toast.emit("Плагины перезагружены.")

    def reload_all(self):
        self.ctx.agents.reload()
        self.ctx.tools.refresh()
        self.refresh()
        self.ctx.events.settings_changed.emit()
        self.ctx.events.toast.emit("Агенты, навыки и плагины перезагружены.")
