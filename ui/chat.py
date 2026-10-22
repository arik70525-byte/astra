"""AI chat with agents, tool approvals and persistent history."""
from __future__ import annotations

import html
import json
from typing import Any, Callable

from markdown_it import MarkdownIt
from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPlainTextEdit, QPushButton, QTextBrowser, QVBoxLayout,
    QWidget,
)

from core.ai import AIClient, AIError, Callbacks, PROVIDER_LABELS
from ui.context import AppContext

md = MarkdownIt("commonmark", {"html": False, "linkify": False})


class ChatInput(QPlainTextEdit):
    send_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent):  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.send_requested.emit()
            return
        super().keyPressEvent(event)


class ChatWorker(QThread):
    delta = Signal(str)
    status = Signal(str)
    tool = Signal(str, object)
    tool_result = Signal(str, str)
    done = Signal(str)
    error = Signal(str)

    def __init__(self, ai: AIClient, messages: list[dict], agent_id: str,
                 model: str, approve: Callable[[str, str], bool], parent=None):
        super().__init__(parent)
        self.ai = ai
        self.messages = messages
        self.agent_id = agent_id
        self.model = model
        self.approve = approve

    def run(self):
        callbacks = Callbacks(
            on_delta=self.delta.emit,
            on_status=self.status.emit,
            on_tool=lambda name, args: self.tool.emit(name, args),
            on_tool_result=lambda name, result: self.tool_result.emit(name, result),
        )
        try:
            text = self.ai.stream_chat(
                self.messages, agent_id=self.agent_id, model=self.model,
                callbacks=callbacks, approve=self.approve,
            )
            self.done.emit(text)
        except AIError as exc:
            self.error.emit(str(exc))
        except Exception as exc:
            self.error.emit(f"Неожиданная ошибка ИИ: {exc}")


class ChatPage(QWidget):
    def __init__(self, ctx: AppContext, approve: Callable[[str, str], bool],
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.approve = approve
        self.chat_id: int | None = None
        self.messages: list[dict[str, str]] = []
        self.stream_text = ""
        self.last_answer = ""
        self.worker: ChatWorker | None = None
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(70)
        self._render_timer.timeout.connect(self._render)
        self._build()
        self.ctx.events.settings_changed.connect(self._refresh_header)
        self.ctx.events.open_chat.connect(self.focus_agent)
        self._refresh_header()
        self._render()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        history = QFrame()
        history.setFixedWidth(248)
        history.setStyleSheet("QFrame { background:#0a0b0e; border-right:1px solid #1e2028; }")
        hist_layout = QVBoxLayout(history)
        hist_layout.setContentsMargins(16, 22, 16, 18)
        hist_layout.setSpacing(10)
        hist_title = QLabel("История")
        hist_title.setObjectName("SectionTitle")
        hist_layout.addWidget(hist_title)
        self.new_btn = QPushButton("＋  Новый чат")
        self.new_btn.setObjectName("Accent")
        self.new_btn.clicked.connect(self.new_chat)
        hist_layout.addWidget(self.new_btn)
        self.history_list = QListWidget()
        self.history_list.currentItemChanged.connect(self._history_selected)
        hist_layout.addWidget(self.history_list, 1)
        delete_chat_btn = QPushButton("Удалить чат")
        delete_chat_btn.setObjectName("Ghost")
        delete_chat_btn.clicked.connect(self.delete_chat)
        hist_layout.addWidget(delete_chat_btn)
        root.addWidget(history)

        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(28, 24, 28, 22)
        main_layout.setSpacing(12)
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("AI Чат")
        title.setObjectName("PageTitle")
        self.meta = QLabel("")
        self.meta.setObjectName("Muted")
        title_box.addWidget(title)
        title_box.addWidget(self.meta)
        header.addLayout(title_box)
        header.addStretch(1)
        self.agent_combo = QComboBox()
        self.agent_combo.setMinimumWidth(220)
        for agent in self.ctx.agents.agents:
            self.agent_combo.addItem(f"{agent.icon}  {agent.name}", agent.id)
        self.agent_combo.currentIndexChanged.connect(self._agent_changed)
        header.addWidget(self.agent_combo)
        main_layout.addLayout(header)

        self.chat_view = QTextBrowser()
        self.chat_view.setObjectName("ChatView")
        self.chat_view.setOpenExternalLinks(True)
        self.chat_view.setOpenLinks(True)
        self.chat_view.setMinimumHeight(280)
        main_layout.addWidget(self.chat_view, 1)

        self.suggestions = QWidget()
        sugg_layout = QHBoxLayout(self.suggestions)
        sugg_layout.setContentsMargins(0, 0, 0, 0)
        sugg_layout.setSpacing(8)
        prompts = [
            "Собери плейлист для работы из моей медиатеки",
            "Проверь публичный домен example.com",
            "Помоги написать Python-скрипт",
        ]
        for prompt in prompts:
            button = QPushButton(prompt)
            button.setObjectName("Chip")
            button.clicked.connect(lambda _=False, p=prompt: self.insert_prompt(p))
            sugg_layout.addWidget(button)
        sugg_layout.addStretch(1)
        main_layout.addWidget(self.suggestions)

        self.status = QLabel("")
        self.status.setObjectName("Tiny")
        main_layout.addWidget(self.status)

        input_frame = QFrame()
        input_frame.setObjectName("Card")
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(12, 10, 12, 10)
        input_layout.setSpacing(8)
        self.input = ChatInput()
        self.input.setPlaceholderText("Сообщение AURA…  Enter — отправить, Shift+Enter — новая строка")
        self.input.setMaximumHeight(130)
        self.input.setMinimumHeight(58)
        self.input.send_requested.connect(self.send)
        input_layout.addWidget(self.input)
        bottom = QHBoxLayout()
        self.model_label = QLabel("")
        self.model_label.setObjectName("Tiny")
        bottom.addWidget(self.model_label)
        bottom.addStretch(1)
        self.speak_btn = QPushButton("🔊")
        self.speak_btn.setObjectName("Ghost")
        self.speak_btn.setToolTip("Озвучить последний ответ локальным голосом Windows")
        self.speak_btn.clicked.connect(self.speak_last)
        bottom.addWidget(self.speak_btn)
        self.send_btn = QPushButton("Отправить  ↗")
        self.send_btn.setObjectName("Accent")
        self.send_btn.clicked.connect(self.send)
        bottom.addWidget(self.send_btn)
        input_layout.addLayout(bottom)
        main_layout.addWidget(input_frame)
        root.addWidget(main, 1)
        self._reload_history()

    def _refresh_header(self):
        provider = str(self.ctx.settings.get("ai.provider", "ollama"))
        model = str(self.ctx.settings.get("ai.model", ""))
        self.meta.setText(
            f"{PROVIDER_LABELS.get(provider, provider)} · {model or 'модель не выбрана'} · "
            f"агентов: {len(self.ctx.agents.agents)}"
        )
        self.model_label.setText(
            f"Модель: {model or 'не выбрана'}   ·   инструменты: {len(self.ctx.tools.names())}"
        )
        current = self.agent_combo.currentData()
        self.agent_combo.blockSignals(True)
        self.agent_combo.clear()
        for agent in self.ctx.agents.agents:
            self.agent_combo.addItem(f"{agent.icon}  {agent.name}", agent.id)
        if current:
            index = self.agent_combo.findData(current)
            if index >= 0:
                self.agent_combo.setCurrentIndex(index)
        self.agent_combo.blockSignals(False)

    def _agent_changed(self, index: int):
        agent_id = self.agent_combo.currentData()
        if self.chat_id is not None and agent_id:
            self.ctx.db.set_chat_agent(int(self.chat_id), str(agent_id))

    def focus_agent(self, agent_id: str):
        index = self.agent_combo.findData(agent_id)
        if index >= 0:
            self.agent_combo.setCurrentIndex(index)
        self.input.setFocus()

    def insert_prompt(self, text: str):
        self.input.setPlainText(text)
        self.input.setFocus()

    def _reload_history(self):
        self.history_list.blockSignals(True)
        self.history_list.clear()
        for chat in self.ctx.db.chats():
            item = QListWidgetItem(f"✦  {chat['title'][:34]}")
            item.setData(Qt.ItemDataRole.UserRole, chat)
            self.history_list.addItem(item)
        self.history_list.blockSignals(False)
        if self.chat_id is not None:
            for index in range(self.history_list.count()):
                item = self.history_list.item(index)
                data = item.data(Qt.ItemDataRole.UserRole)
                if data and int(data["id"]) == int(self.chat_id):
                    self.history_list.setCurrentItem(item)
                    break

    def _history_selected(self, current: QListWidgetItem | None, previous=None):
        if current is None:
            return
        chat = current.data(Qt.ItemDataRole.UserRole)
        if not chat:
            return
        self.chat_id = int(chat["id"])
        self.messages = [
            {"role": item["role"], "content": item["content"]}
            for item in self.ctx.db.chat_messages(self.chat_id)
            if item["role"] in ("user", "assistant")
        ]
        self.stream_text = ""
        index = self.agent_combo.findData(chat.get("agent_id") or "assistant")
        if index >= 0:
            self.agent_combo.blockSignals(True)
            self.agent_combo.setCurrentIndex(index)
            self.agent_combo.blockSignals(False)
        self.suggestions.setVisible(not self.messages)
        self._render()

    def new_chat(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "AURA", "Дождитесь завершения текущего ответа.")
            return
        self.chat_id = None
        self.messages = []
        self.stream_text = ""
        self.history_list.clearSelection()
        self.suggestions.setVisible(True)
        self.status.setText("")
        self._render()
        self.input.setFocus()

    def delete_chat(self):
        item = self.history_list.currentItem()
        if not item:
            return
        chat = item.data(Qt.ItemDataRole.UserRole)
        if not chat:
            return
        if QMessageBox.question(self, "Удалить чат", f"Удалить «{chat['title']}»?") != QMessageBox.StandardButton.Yes:
            return
        self.ctx.db.delete_chat(int(chat["id"]))
        if self.chat_id == int(chat["id"]):
            self.new_chat()
        self._reload_history()

    def send(self):
        text = self.input.toPlainText().strip()
        if not text:
            return
        if self.worker and self.worker.isRunning():
            self.status.setText("AURA ещё отвечает…")
            return
        if self.chat_id is None:
            title = text.replace("\n", " ")[:60] or "Новый чат"
            self.chat_id = self.ctx.db.create_chat(title, str(self.agent_combo.currentData() or "assistant"))
            self._reload_history()
        self.ctx.db.add_message(self.chat_id, "user", text)
        self.messages.append({"role": "user", "content": text})
        self.input.clear()
        self.suggestions.setVisible(False)
        self.stream_text = ""
        self.status.setText("Думаю…")
        self.send_btn.setEnabled(False)
        self.input.setEnabled(False)
        history = list(self.messages)
        model = str(self.ctx.settings.get("ai.model", ""))
        self.worker = ChatWorker(
            self.ctx.ai, history, str(self.agent_combo.currentData() or "assistant"),
            model, self.approve, self,
        )
        self.worker.delta.connect(self._delta)
        self.worker.status.connect(self._status)
        self.worker.tool.connect(self._tool)
        self.worker.tool_result.connect(self._tool_result)
        self.worker.done.connect(self._done)
        self.worker.error.connect(self._error)
        self.worker.start()
        self._render()

    def _delta(self, text: str):
        self.stream_text += text
        self._schedule_render()

    def _status(self, text: str):
        self.status.setText(text)

    def _tool(self, name: str, args: dict):
        args_text = json.dumps(args, ensure_ascii=False)
        if len(args_text) > 500:
            args_text = args_text[:500] + "…"
        self.stream_text += f"\n\n> ⚙ **{name}**\n> `{args_text}`\n"
        self._schedule_render()

    def _tool_result(self, name: str, result: str):
        first = (result or "").strip().splitlines()
        preview = first[0][:300] if first else ""
        self.stream_text += f"> ↳ {preview}\n"
        self._schedule_render()

    def _done(self, text: str):
        final = (text or "").strip() or self.stream_text.strip() or "Готово."
        self.last_answer = final
        self.messages.append({"role": "assistant", "content": final})
        if self.chat_id is not None:
            self.ctx.db.add_message(self.chat_id, "assistant", final)
        self.stream_text = ""
        self.status.setText("")
        self.send_btn.setEnabled(True)
        self.input.setEnabled(True)
        self.input.setFocus()
        self._reload_history()
        self._render()
        autospeak = bool(self.ctx.settings.get("ai.autospeak", False)) or bool(
            self.ctx.settings.get("voice.autospeak", False)
        )
        if autospeak and self.ctx.tts:
            self.ctx.tts.speak(final)

    def speak_last(self):
        text = self.last_answer or self.stream_text
        if not text:
            for message in reversed(self.messages):
                if message.get("role") == "assistant":
                    text = message.get("content") or ""
                    break
        if not text:
            self.status.setText("Нет ответа для озвучки.")
            return
        if self.ctx.tts:
            self.ctx.tts.speak(text)
            self.status.setText("Озвучиваю ответ…")
        else:
            self.status.setText("TTS недоступен.")

    def _error(self, message: str):
        text = f"**Ошибка:** {message}"
        self.messages.append({"role": "assistant", "content": text})
        if self.chat_id is not None:
            self.ctx.db.add_message(self.chat_id, "assistant", text)
        self.stream_text = ""
        self.status.setText("Ошибка — проверьте Настройки → Локальный ИИ")
        self.send_btn.setEnabled(True)
        self.input.setEnabled(True)
        self._render()

    def _schedule_render(self):
        if not self._render_timer.isActive():
            self._render_timer.start()

    def _bubble(self, role: str, content: str, cursor: bool = False) -> str:
        """Qt rich text has no flexbox; tables give a reliable chat layout."""
        if role == "user":
            inner = html.escape(content).replace("\n", "<br>")
            return (
                "<table width='100%' cellspacing='0' cellpadding='5'><tr>"
                "<td width='30'></td>"
                "<td width='100%' align='right'>"
                "<table width='92%' cellspacing='0' cellpadding='10' bgcolor='#29240f'><tr>"
                f"<td style='color:#fff4c9;'>{inner}</td></tr></table></td>"
                "<td width='46' align='right' valign='top'>"
                "<table cellspacing='0' cellpadding='5' bgcolor='#33353f'><tr>"
                "<td class='avatar' style='color:#e9e9ee;'>Вы</td></tr></table></td>"
                "</tr></table>"
            )
        inner = md.render(content)
        if cursor:
            inner += "<span class='cursor'>▍</span>"
        return (
            "<table width='100%' cellspacing='0' cellpadding='5'><tr>"
            "<td width='42' valign='top'>"
            "<table cellspacing='0' cellpadding='5' bgcolor='#ffd54a'><tr>"
            "<td class='avatar' style='color:#15120a;'>✦</td></tr></table></td>"
            "<td width='100%' align='left'>"
            "<table width='92%' cellspacing='0' cellpadding='10' bgcolor='#17181e'><tr>"
            f"<td>{inner}</td></tr></table></td>"
            "<td width='18'></td>"
            "</tr></table>"
        )

    def _render(self):
        body: list[str] = []
        if not self.messages and not self.stream_text:
            body.append(
                "<div class='welcome'><div class='orb'>✦</div>"
                "<h1>Чем помочь?</h1>"
                "<p>Спросите о музыке, файлах, коде или публичных данных. "
                "AURA видит только разрешённые папки и спрашивает подтверждение "
                "перед записью, терминалом, песочницей и OSINT-запросами.</p></div>"
            )
        for message in self.messages:
            role = message.get("role")
            content = message.get("content") or ""
            body.append(self._bubble(role, content))
        if self.stream_text or (self.worker and self.worker.isRunning()):
            body.append(
                self._bubble("assistant", self.stream_text or "…", cursor=True)
            )
        css = """
        <style>
        body { background:#0d0e12; color:#ececf1; font-family:'Segoe UI'; font-size:14px; }
        td { line-height:1.5; }
        h1 { color:#fff; font-size:27px; margin:6px 0 10px; }
        h2 { color:#fff; font-size:19px; }
        p { margin:7px 0; }
        a { color:#ffd54a; }
        code { background:#0c0d10; color:#ffd98a; padding:2px 5px; font-family:Consolas; }
        pre { background:#0a0b0e; border:1px solid #272a33; padding:11px; }
        pre code { padding:0; background:transparent; color:#d9e7d4; }
        blockquote { border-left:3px solid #ffd54a; margin:7px 0; padding:2px 10px; color:#c9c1a5; background:#131419; }
        .welcome { text-align:center; padding:58px 30px 30px; }
        .welcome p { color:#9b9eaa; }
        .orb { font-size:44px; color:#ffd54a; }
        .cursor { color:#ffd54a; }
        .avatar { font-size:11px; font-weight:700; }
        </style>
        """
        self.chat_view.setHtml(css + "".join(body))
        self.chat_view.verticalScrollBar().setValue(self.chat_view.verticalScrollBar().maximum())
