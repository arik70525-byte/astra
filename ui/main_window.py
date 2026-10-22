"""Main window, sidebar, navigation and global shortcuts."""
from __future__ import annotations

import sys
import threading

from PySide6.QtCore import (
    QEasingCurve, QObject, QProcess, QPropertyAnimation, Qt, QTimer, Signal,
)
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QDialog, QFrame, QGraphicsOpacityEffect,
    QHBoxLayout, QInputDialog, QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from core.auth import AuthManager
from core.ai import PROVIDER_LABELS
from core.config import APP_VERSION
from core.demo_music import demo_pack_exists
from core.i18n import language, tr
from core.voice import GlobalHotkey
from ui.admin_page import AdminPage
from ui.agents_page import AgentsPage
from ui.chat import ChatPage
from ui.context import AppContext
from ui.home import HomePage
from ui.library import DemoPackWorker, LibraryPage
from ui.osint_page import OsintPage
from ui.pc_page import PcPage
from ui.player_bar import PlayerBar
from ui.search import SearchPage
from ui.settings_page import SettingsPage
from ui.studio_page import StudioPage
from ui.terminal_page import TerminalPage
from ui.theme import apply_theme
from ui.voice_page import VoicePage

WORKSPACES: dict[str, dict] = {
    "player": {
        "label": "workspace.player",
        "pages": ("home", "search", "library"),
        "default": "home",
    },
    "sandbox": {
        "label": "workspace.sandbox",
        "pages": ("terminal",),
        "default": "terminal",
    },
    "osint": {
        "label": "workspace.osint",
        "pages": ("osint",),
        "default": "osint",
    },
    "chat": {
        "label": "workspace.chat",
        "pages": ("chat", "agents", "studio", "voice"),
        "default": "chat",
    },
    "pc": {
        "label": "workspace.pc",
        "pages": ("pc",),
        "default": "pc",
    },
    "admin": {
        "label": "workspace.admin",
        "pages": ("admin",),
        "default": "admin",
    },
    "all": {
        "label": "workspace.all",
        "pages": (),
        "default": "",
    },
}

PAGE_WORKSPACE = {
    "home": "player", "search": "player", "library": "player",
    "terminal": "sandbox",
    "osint": "osint",
    "chat": "chat", "agents": "chat", "studio": "chat", "voice": "chat",
    "pc": "pc",
    "admin": "admin",
}


class ApprovalBridge(QObject):
    requested = Signal(str, str, object, object)


class QueueDialog(QDialog):
    def __init__(self, ctx: AppContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Очередь воспроизведения")
        self.resize(640, 560)
        layout = QVBoxLayout(self)
        title = QLabel("Очередь")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _: self._play())
        layout.addWidget(self.list, 1)
        self.count = QLabel("")
        self.count.setObjectName("Tiny")
        layout.addWidget(self.count)
        row = QHBoxLayout()
        play = QPushButton("Играть выбранное")
        play.setObjectName("Accent")
        play.clicked.connect(self._play)
        remove = QPushButton("Убрать")
        remove.clicked.connect(self._remove)
        save = QPushButton("Сохранить как плейлист")
        save.setObjectName("Ghost")
        save.clicked.connect(self._save)
        clear = QPushButton("Очистить")
        clear.setObjectName("Ghost")
        clear.clicked.connect(self._clear)
        close = QPushButton("Закрыть")
        close.setObjectName("Ghost")
        close.clicked.connect(self.accept)
        row.addWidget(play)
        row.addWidget(remove)
        row.addWidget(save)
        row.addWidget(clear)
        row.addStretch(1)
        row.addWidget(close)
        layout.addLayout(row)
        self.ctx.player.queue_changed.connect(self._load)
        self._load(self.ctx.player.queue)

    def _load(self, queue):
        current = self.ctx.player.current
        current_id = current.get("id") if current else None
        self.list.clear()
        for track in queue:
            marker = "▶  " if current_id is not None and track.get("id") == current_id else "    "
            item = QListWidgetItem(
                f"{marker}{track.get('artist') or ''} — {track.get('title') or ''}"
            )
            item.setData(Qt.ItemDataRole.UserRole, track)
            self.list.addItem(item)
        self.count.setText(f"{len(queue)} треков · текущий: " + (
            f"{current.get('artist') or ''} — {current.get('title') or ''}" if current else "—"
        ))

    def _play(self):
        row = self.list.currentRow()
        if row < 0:
            return
        self.ctx.player.queue and self.ctx.player.play_tracks(self.ctx.player.queue, row)

    def _remove(self):
        row = self.list.currentRow()
        if row >= 0:
            self.ctx.player.remove_from_queue(row)

    def _save(self):
        queue = list(self.ctx.player.queue)
        if not queue:
            return
        name, ok = QInputDialog.getText(self, "Плейлист", "Название нового плейлиста:")
        if not ok or not name.strip():
            return
        playlist_id = self.ctx.db.create_playlist(name.strip(), source="queue")
        added = 0
        for track in queue:
            if track.get("id") is None:
                continue
            self.ctx.db.add_to_playlist(playlist_id, int(track["id"]))
            added += 1
        self.ctx.events.library_changed.emit()
        QMessageBox.information(self, "Плейлист", f"Сохранено треков: {added}")

    def _clear(self):
        if not self.ctx.player.queue:
            return
        answer = QMessageBox.question(
            self, "Очередь", "Очистить очередь? Текущее воспроизведение остановится."
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        for position in range(len(self.ctx.player.queue) - 1, -1, -1):
            self.ctx.player.remove_from_queue(position)


class MainWindow(QMainWindow):
    def __init__(
        self,
        ctx: AppContext,
        user: dict | None = None,
        auth: AuthManager | None = None,
        start_workspace: str = "player",
    ):
        super().__init__()
        self.ctx = ctx
        self.user = user
        self.auth = auth
        self._workspace = start_workspace if start_workspace in WORKSPACES else "player"
        self.bridge = ApprovalBridge(self)
        self.bridge.requested.connect(self._show_approval)
        self.setWindowTitle(f"AURA Studio {APP_VERSION}")
        self.resize(1440, 900)
        self.setMinimumSize(1080, 700)
        self._fade_anim: QPropertyAnimation | None = None
        self._faded_page: QWidget | None = None
        self._demo_worker: DemoPackWorker | None = None
        self._build()
        self._wire_events()
        self._shortcuts()
        self._apply_language()
        self.set_workspace(self._workspace)
        self._update_sidebar()
        QTimer.singleShot(900, self._maybe_autostart_server)
        self._server_timer = QTimer(self)
        self._server_timer.setInterval(2500)
        self._server_timer.timeout.connect(self._update_sidebar)
        self._server_timer.start()
        self.hotkey = GlobalHotkey(self)
        self.hotkey.pressed.connect(self._hotkey_pressed)
        self.hotkey.registered.connect(self._hotkey_registered)
        QTimer.singleShot(800, self._register_hotkey)
        QTimer.singleShot(1600, self._maybe_seed_demo)

    def _build(self):
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)
        self.stack = QStackedWidget()
        self.stack.setObjectName("Pages")
        self.pages = {
            "home": HomePage(self.ctx),
            "search": SearchPage(self.ctx),
            "library": LibraryPage(self.ctx),
            "chat": ChatPage(self.ctx, self.request_approval),
            "agents": AgentsPage(self.ctx),
            "osint": OsintPage(self.ctx),
            "studio": StudioPage(self.ctx),
            "voice": VoicePage(self.ctx, self.request_approval),
            "terminal": TerminalPage(self.ctx),
            "pc": PcPage(self.ctx),
            "settings": SettingsPage(self.ctx),
        }
        if self.auth is not None and self.user and self.user.get("role") == "admin":
            self.pages["admin"] = AdminPage(self.auth, self.user, self.ctx.settings)
        content.addWidget(self._build_sidebar())
        for page in self.pages.values():
            self.stack.addWidget(page)
        content.addWidget(self.stack, 1)
        outer.addLayout(content, 1)
        self.player_bar = PlayerBar(self.ctx)
        self.player_bar.queue_requested.connect(self._open_queue)
        outer.addWidget(self.player_bar)
        self.setCentralWidget(central)
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().setStyleSheet(
            "QStatusBar { background:#090a0d; color:#8e919d; border-top:1px solid #1c1e25; "
            "font-size:11px; padding:2px 12px; }"
        )
        self.statusBar().showMessage("Готово")

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(232)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 22, 16, 16)
        layout.setSpacing(4)
        logo_row = QHBoxLayout()
        logo = QLabel("AURA")
        logo.setObjectName("Logo")
        dot = QLabel(".")
        dot.setObjectName("LogoDot")
        logo_row.addWidget(logo)
        logo_row.addWidget(dot)
        logo_row.addStretch(1)
        layout.addLayout(logo_row)
        self.tagline = QLabel(tr(self.ctx.settings, "app.tagline"))
        self.tagline.setObjectName("Tiny")
        self.tagline.setStyleSheet("letter-spacing:1.5px; color:#5f626e; font-size:9px;")
        layout.addWidget(self.tagline)
        layout.addSpacing(14)

        self.workspace_caption = QLabel(tr(self.ctx.settings, "workspace.label"))
        self.workspace_caption.setStyleSheet(
            "color:#555863; font-size:9px; font-weight:700; letter-spacing:1.4px; "
            "padding:0 4px 3px 4px;"
        )
        layout.addWidget(self.workspace_caption)
        self.workspace_combo = QComboBox()
        self.workspace_combo.setObjectName("WorkspaceCombo")
        self.workspace_combo.setToolTip("Контекстное меню разделов")
        for key, icon in (
            ("player", "♫"), ("sandbox", "⌘"), ("osint", "◎"),
            ("chat", "✦"), ("pc", "▣"),
        ):
            self.workspace_combo.addItem(
                f"{icon}  {tr(self.ctx.settings, WORKSPACES[key]['label'])}", key
            )
        if "admin" in getattr(self, "pages", {}):
            self.workspace_combo.addItem(
                "⚙  " + tr(self.ctx.settings, "workspace.admin"), "admin"
            )
        self.workspace_combo.addItem(
            "▦  " + tr(self.ctx.settings, "workspace.all"), "all"
        )
        self.workspace_combo.currentIndexChanged.connect(self._workspace_combo_changed)
        layout.addWidget(self.workspace_combo)
        layout.addSpacing(10)

        self.nav_buttons: dict[str, QPushButton] = {}
        self.nav_meta: dict[str, tuple[str, str]] = {}
        self.nav_labels: dict[str, QLabel] = {}
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        sections = [
            ("nav.library", [
                ("home", "⌂", "nav.home"),
                ("search", "⌕", "nav.search"),
                ("library", "▤", "nav.library_page"),
            ]),
            ("nav.ai", [
                ("chat", "✦", "nav.chat"),
                ("agents", "◈", "nav.agents"),
                ("studio", "◧", "nav.studio"),
                ("voice", "◉", "nav.voice"),
            ]),
            ("nav.tools", [
                ("osint", "◎", "nav.osint"),
                ("terminal", "⌘", "nav.terminal"),
                ("pc", "▣", "nav.pc"),
            ]),
        ]
        for section_key, items in sections:
            label = self._nav_label(section_key)
            layout.addWidget(label)
            self.nav_labels[section_key] = label
            for key, icon, text_key in items:
                layout.addWidget(self._nav_button(key, icon, text_key))
            layout.addSpacing(10)
        if "admin" in getattr(self, "pages", {}):
            self.nav_labels["nav.admin"] = self._nav_label("nav.admin")
            layout.addWidget(self.nav_labels["nav.admin"])
            layout.addWidget(self._nav_button("admin", "⚙", "workspace.admin"))
        layout.addStretch(1)

        user_card = QFrame()
        user_card.setObjectName("SoftCard")
        u = QHBoxLayout(user_card)
        u.setContentsMargins(9, 8, 9, 8)
        u.setSpacing(8)
        avatar = QLabel()
        avatar.setFixedSize(28, 28)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(
            "background:#2a2133; border:1px solid #45364f; border-radius:14px; "
            "font-weight:700; font-size:11px; color:#ff9bdc;"
        )
        name = str((self.user or {}).get("display_name") or (self.user or {}).get("username") or "AURA")
        avatar.setText(name[:1].upper())
        u.addWidget(avatar)
        user_text = QVBoxLayout()
        user_text.setSpacing(0)
        self.user_name = QLabel(name if self.user else tr(self.ctx.settings, "common.local_user"))
        self.user_name.setStyleSheet("font-size:11px; font-weight:650;")
        self.user_role = QLabel(
            (tr(self.ctx.settings, "admin.role_admin") if (self.user or {}).get("role") == "admin"
             else tr(self.ctx.settings, "admin.role_user")) if self.user else "AURA Studio"
        )
        self.user_role.setObjectName("Tiny")
        user_text.addWidget(self.user_name)
        user_text.addWidget(self.user_role)
        u.addLayout(user_text, 1)
        self.logout_btn = QPushButton("⇥")
        self.logout_btn.setObjectName("Ghost")
        self.logout_btn.setFixedSize(26, 26)
        self.logout_btn.setToolTip(tr(self.ctx.settings, "common.logout"))
        self.logout_btn.clicked.connect(self._logout)
        self.logout_btn.setVisible(bool(self.auth and self.user))
        u.addWidget(self.logout_btn)
        layout.addWidget(user_card)
        layout.addSpacing(8)

        status_card = QFrame()
        status_card.setObjectName("SoftCard")
        card_layout = QVBoxLayout(status_card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(3)
        self.side_ai = QLabel("AI: —")
        self.side_ai.setStyleSheet("font-weight:600; font-size:11px;")
        self.side_model = QLabel("")
        self.side_model.setObjectName("Tiny")
        self.side_model.setWordWrap(True)
        self.side_access = QLabel("")
        self.side_access.setObjectName("Tiny")
        self.side_server = QLabel("")
        self.side_server.setObjectName("Tiny")
        for label in (self.side_ai, self.side_model, self.side_access, self.side_server):
            card_layout.addWidget(label)
        layout.addWidget(status_card)
        layout.addSpacing(8)
        layout.addWidget(self._nav_button("settings", "⚙", "nav.settings"))
        self.version_label = QLabel(f"v{APP_VERSION} · Windows")
        self.version_label.setObjectName("Tiny")
        self.version_label.setStyleSheet("color:#4f525d; font-size:9px; padding-left:10px;")
        layout.addWidget(self.version_label)
        return sidebar

    def _nav_label(self, key: str) -> QLabel:
        label = QLabel(tr(self.ctx.settings, key))
        label.setStyleSheet(
            "color:#555863; font-size:9px; font-weight:700; letter-spacing:1.4px; "
            "padding:8px 12px 4px 12px;"
        )
        return label

    def _nav_button(self, key: str, icon: str, text_key: str) -> QPushButton:
        button = QPushButton(f"{icon}   {tr(self.ctx.settings, text_key)}")
        button.setObjectName("Nav")
        button.setCheckable(True)
        button.clicked.connect(lambda _=False, k=key: self.set_page(k))
        self.nav_group.addButton(button)
        self.nav_buttons[key] = button
        self.nav_meta[key] = (icon, text_key)
        return button

    def _workspace_combo_changed(self, index: int):
        key = str(self.workspace_combo.itemData(index) or "")
        if key and key != self._workspace:
            self.set_workspace(key)

    def _allowed_pages(self) -> set[str]:
        if self._workspace == "all":
            return set(self.pages)
        spec = WORKSPACES.get(self._workspace, WORKSPACES["player"])
        return {key for key in spec["pages"] if key in self.pages}

    def set_workspace(self, key: str):
        if key not in WORKSPACES or (key == "admin" and "admin" not in self.pages):
            key = "player"
        self._workspace = key
        index = self.workspace_combo.findData(key)
        if index >= 0:
            self.workspace_combo.blockSignals(True)
            self.workspace_combo.setCurrentIndex(index)
            self.workspace_combo.blockSignals(False)
        allowed = self._allowed_pages()
        self._apply_workspace_visibility(allowed)
        if key == "all":
            return
        current = self.stack.currentWidget()
        current_key = next(
            (page_key for page_key, page in self.pages.items() if page is current), None
        )
        if current_key is not None and current_key in allowed:
            return
        target = str(WORKSPACES[key].get("default") or "")
        if target in self.pages:
            self.set_page(target)

    def _apply_workspace_visibility(self, allowed: set[str]):
        sections = {
            "nav.library": {"home", "search", "library"},
            "nav.ai": {"chat", "agents", "studio", "voice"},
            "nav.tools": {"osint", "terminal", "pc"},
            "nav.admin": {"admin"},
        }
        for key, button in self.nav_buttons.items():
            button.setVisible(key in allowed or key == "settings")
        for section, pages in sections.items():
            label = self.nav_labels.get(section)
            if label is not None:
                label.setVisible(bool(pages & allowed))

    def _ensure_page_visible(self, key: str):
        if key == "settings" or self._workspace == "all":
            return
        if key in self._allowed_pages():
            return
        target = PAGE_WORKSPACE.get(key)
        if target in WORKSPACES and (target != "admin" or "admin" in self.pages):
            self.set_workspace(target)

    def _apply_language(self):
        settings = self.ctx.settings
        for key, (icon, text_key) in self.nav_meta.items():
            button = self.nav_buttons.get(key)
            if button is not None:
                button.setText(f"{icon}   {tr(settings, text_key)}")
        for key, label in self.nav_labels.items():
            label.setText(tr(settings, key))
        self.tagline.setText(tr(settings, "app.tagline"))
        self.workspace_caption.setText(tr(settings, "workspace.label"))
        icons = {
            "player": "♫", "sandbox": "⌘", "osint": "◎", "chat": "✦",
            "pc": "▣", "admin": "⚙", "all": "▦",
        }
        for index in range(self.workspace_combo.count()):
            key = str(self.workspace_combo.itemData(index) or "")
            if key in WORKSPACES:
                self.workspace_combo.setItemText(
                    index, f"{icons.get(key, '•')}  {tr(settings, WORKSPACES[key]['label'])}"
                )
        if self.user:
            self.user_role.setText(
                tr(settings, "admin.role_admin") if self.user.get("role") == "admin"
                else tr(settings, "admin.role_user")
            )
        else:
            self.user_name.setText(tr(settings, "common.local_user"))
        self.logout_btn.setToolTip(tr(settings, "common.logout"))

    def _logout(self):
        if not self.auth or not self.user:
            return
        answer = QMessageBox.question(
            self, "Смена пользователя",
            "Выйти из аккаунта? AURA перезапустится и снова покажет вход.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.ctx.server.stop()
        except Exception:
            pass
        self.close()
        args = list(sys.argv[1:]) if getattr(sys, "frozen", False) else list(sys.argv)
        QProcess.startDetached(sys.executable, args)
        QApplication.quit()

    def _wire_events(self):
        events = self.ctx.events
        events.open_settings.connect(lambda: self.set_page("settings"))
        events.navigate.connect(self.set_page)
        events.open_chat.connect(self._open_chat)
        events.toast.connect(lambda message: self.statusBar().showMessage(message, 7000))
        events.settings_changed.connect(self._settings_changed)
        events.library_changed.connect(self._library_changed)
        events.voice_prompt.connect(self._voice_prompt)
        events.ask_ai.connect(self._ask_ai)
        events.voice_listen.connect(self._start_voice_listen)
        events.accent_changed.connect(self._accent_changed)
        self.ctx.player.external_requested.connect(self._external_track)
        if self.ctx.tts:
            self.ctx.tts.started.connect(
                lambda text: self.statusBar().showMessage("AURA говорит: " + text, 6000)
            )

    def _shortcuts(self):
        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: (self.set_page("search"),
                                                                  self.pages["search"].query.setFocus()))
        QShortcut(QKeySequence("Ctrl+Space"), self, activated=self.ctx.player.toggle)
        QShortcut(QKeySequence("Ctrl+Right"), self, activated=self.ctx.player.next)
        QShortcut(QKeySequence("Ctrl+Left"), self, activated=self.ctx.player.previous)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=lambda: self.set_page("settings"))
        QShortcut(QKeySequence("Ctrl+Shift+V"), self, activated=self._start_voice_listen)
        for index, key in enumerate(
            ["home", "search", "library", "chat", "agents", "studio", "voice", "osint", "terminal"],
            start=1,
        ):
            QShortcut(QKeySequence(f"Ctrl+{index}"), self, activated=lambda k=key: self.set_page(k))

    def set_page(self, key: str):
        page = self.pages.get(key)
        if page is None:
            return
        self._ensure_page_visible(key)
        self.stack.setCurrentWidget(page)
        if bool(self.ctx.settings.get("ui.animations", True)):
            self._animate_page(page)
        button = self.nav_buttons.get(key)
        if button:
            button.setChecked(True)
        if hasattr(page, "refresh") and key in ("home", "library", "admin"):
            try:
                page.refresh()
            except Exception:
                pass
        if key == "settings":
            self.pages["settings"].load()
        if key == "voice":
            try:
                page._refresh_model_state()
            except Exception:
                pass
        if key == "chat":
            self.pages["chat"].input.setFocus()

    def _animate_page(self, page: QWidget):
        try:
            if self._fade_anim is not None:
                self._fade_anim.stop()
            if self._faded_page is not None:
                self._faded_page.setGraphicsEffect(None)
            self._faded_page = page
            effect = QGraphicsOpacityEffect(page)
            page.setGraphicsEffect(effect)
            anim = QPropertyAnimation(effect, b"opacity", self)
            anim.setDuration(190)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.finished.connect(lambda p=page: p.setGraphicsEffect(None))
            self._fade_anim = anim
            anim.start()
        except Exception:
            page.setGraphicsEffect(None)

    def _open_chat(self, agent_id: str):
        self.set_page("chat")
        chat = self.pages["chat"]
        chat.focus_agent(agent_id)
        chat.new_chat()

    def _voice_prompt(self, prompt: str):
        chat = self.pages.get("chat")
        if not chat:
            return
        self.set_page("chat")
        chat.insert_prompt(prompt)
        QTimer.singleShot(80, chat.send)

    def _ask_ai(self, prompt: str):
        chat = self.pages.get("chat")
        if not chat:
            return
        self.set_page("chat")
        chat.insert_prompt(prompt)
        chat.input.setFocus()

    def _start_voice_listen(self):
        self.set_page("voice")
        QTimer.singleShot(100, self.pages["voice"].start_listening)

    def _hotkey_pressed(self):
        self._start_voice_listen()

    def _register_hotkey(self):
        spec = str(self.ctx.settings.get("voice.hotkey", "Ctrl+Alt+Space") or "Ctrl+Alt+Space")
        self.hotkey.stop()
        self.hotkey.start(spec)

    def _hotkey_registered(self, ok: bool, message: str):
        if ok:
            self.statusBar().showMessage(
                f"Голосовая клавиша активна: {self.ctx.settings.get('voice.hotkey', message)}",
                5000,
            )
        else:
            self.statusBar().showMessage(
                "Глобальная клавиша недоступна: " + message + " (Ctrl+Shift+V работает в окне AURA).",
                9000,
            )

    def _maybe_seed_demo(self):
        if not bool(self.ctx.settings.get("library.auto_demo", True)):
            return
        if demo_pack_exists(self.ctx.db):
            return
        if self._demo_worker and self._demo_worker.isRunning():
            return
        worker = DemoPackWorker(self.ctx.settings, self.ctx.db, parent=self)
        self._demo_worker = worker

        def done(result: dict):
            self.ctx.events.library_changed.emit()
            self.statusBar().showMessage(
                f"Демо-альбом AURA готов: {result.get('created', 0)} треков.", 8000
            )

        def failed(message: str):
            self.statusBar().showMessage("Демо-альбом не создан: " + message, 9000)

        worker.done.connect(done)
        worker.error.connect(failed)
        worker.start()
        self.statusBar().showMessage("Генерирую оригинальный демо-альбом AURA…", 5000)

    def _settings_changed(self):
        self.ctx.agents.reload()
        self.ctx.tools.refresh()
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, str(self.ctx.settings.get("ui.accent", "sunset")))
        self._register_hotkey()
        self._apply_language()
        self._update_sidebar()
        home = self.pages.get("home")
        if home:
            home.refresh()
        agents = self.pages.get("agents")
        if agents:
            agents.refresh()
        chat = self.pages.get("chat")
        if chat:
            chat._refresh_header()
        admin = self.pages.get("admin")
        if admin:
            admin.refresh()
        voice = self.pages.get("voice")
        if voice:
            try:
                voice._refresh_model_state()
            except Exception:
                pass

    def _accent_changed(self, _accent: str):
        self.pages["home"].orb.update()

    def _library_changed(self):
        home = self.pages.get("home")
        if home:
            home.refresh()

    def _update_sidebar(self):
        provider = str(self.ctx.settings.get("ai.provider", "ollama"))
        model = str(self.ctx.settings.get("ai.model", ""))
        self.side_ai.setText(f"AI · {PROVIDER_LABELS.get(provider, provider)}")
        self.side_model.setText(model or "модель не выбрана")
        roots = len(self.ctx.tools.policy.roots)
        if roots % 10 == 1 and roots % 100 != 11:
            folder_word = "папка"
        elif roots % 10 in (2, 3, 4) and roots % 100 not in (12, 13, 14):
            folder_word = "папки"
        else:
            folder_word = "папок"
        self.side_access.setText(
            f"● доступ: {roots} {folder_word}"
            + (", запись" if self.ctx.tools.policy.allow_write else "")
            + (", терминал" if self.ctx.tools.policy.allow_shell else "")
        )
        self.side_server.setText(
            f"● сервер: {'LAN' if self.ctx.server.running else 'выкл'}"
            if self.ctx.server.running else "○ локальный сервер выкл"
        )
        self.side_server.setStyleSheet("font-size:10px; color:#5bdd9a;" if self.ctx.server.running else "font-size:10px; color:#6f7280;")

    def _maybe_autostart_server(self):
        if self.ctx.settings.get("server.autostart", False):
            result = self.ctx.server.start(
                int(self.ctx.settings.get("server.port", 8765)),
                bool(self.ctx.settings.get("server.lan", False)),
            )
            if result.get("ok"):
                self.statusBar().showMessage(
                    "Локальный сервер запущен: " + str(result.get("url")), 8000
                )
            else:
                self.statusBar().showMessage("Сервер не запустился: " + str(result.get("error")), 10000)
            self._update_sidebar()

    def _open_queue(self):
        QueueDialog(self.ctx, self).exec()

    def _external_track(self, track: dict):
        url = str(track.get("external_url") or "")
        if not url:
            self.statusBar().showMessage("У трека нет внешней ссылки.", 5000)
            return
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl(url))
        self.statusBar().showMessage("Ссылка открыта в браузере.", 5000)

    def request_approval(self, title: str, details: str) -> bool:
        event = threading.Event()
        result: dict = {"ok": False}
        self.bridge.requested.emit(title, details, event, result)
        if not event.wait(310):
            return False
        return bool(result.get("ok"))

    def _show_approval(self, title: str, details: str, event, result: dict):
        box = QMessageBox(self)
        box.setWindowTitle("Подтверждение AURA")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(title)
        box.setInformativeText(
            "ИИ просит выполнить действие. Проверьте детали и разрешите только то, "
            "что понимаете."
        )
        box.setDetailedText(details)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        box.button(QMessageBox.StandardButton.Yes).setText("Разрешить")
        box.button(QMessageBox.StandardButton.No).setText("Запретить")
        result["ok"] = box.exec() == QMessageBox.StandardButton.Yes
        event.set()

    def closeEvent(self, event):  # noqa: N802
        for shutdown in (
            lambda: self.hotkey.stop(),
            lambda: self.ctx.server.stop(),
            lambda: self.pages["terminal"].shutdown(),
            lambda: self.pages["settings"].shutdown(),
            lambda: self.pages["voice"].shutdown(),
            lambda: self.pages["studio"].shutdown(),
        ):
            try:
                shutdown()
            except Exception:
                pass
        chat = self.pages.get("chat")
        if chat and chat.worker and chat.worker.isRunning():
            chat.worker.wait(2500)
        if self._demo_worker and self._demo_worker.isRunning():
            self._demo_worker.cancelled = True
            self._demo_worker.wait(2500)
        try:
            self.ctx.player.shutdown()
        except Exception:
            pass
        try:
            self.ctx.db.close()
        except Exception:
            pass
        super().closeEvent(event)
