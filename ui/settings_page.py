"""Local-first settings: AI models, access, voice, media and LAN server.

There are deliberately no cloud API-key fields here.  AURA 1.1 runs on local
Ollama models (exactly two managed choices), offline Vosk speech recognition
and Windows SAPI speech output.  Legacy cloud/OAuth secrets can only be erased
with an explicit confirmation.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QSpinBox,
    QVBoxLayout, QWidget,
)

from core.config import (
    APP_VERSION, DATA_DIR, DOWNLOADS_DIR, GENERATED_DIR, LEGACY_API_SECRETS,
    MUSIC_DIR, VOICE_DIR,
)
from core.i18n import LANGUAGES
from core.local_ai import MANAGED_MODELS, LocalAIError, OllamaManager, model_info
from ui.context import AppContext
from ui.theme import PALETTES, apply_theme


class LocalAIStatusWorker(QThread):
    done = Signal(dict)

    def __init__(self, manager: OllamaManager, parent=None):
        super().__init__(parent)
        self.manager = manager

    def run(self):
        try:
            self.done.emit(self.manager.status())
        except Exception as exc:
            self.done.emit({"ok": False, "error": str(exc), "models": []})


class ModelPullWorker(QThread):
    progress = Signal(int, int, str)
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, manager: OllamaManager, model_id: str, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.model_id = model_id
        self.cancelled = False

    def run(self):
        try:
            result = self.manager.pull(
                self.model_id,
                progress=lambda i, total, text: self.progress.emit(i, total, text),
                cancelled=lambda: self.cancelled,
            )
            self.done.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class ModelActivateWorker(QThread):
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, manager: OllamaManager, model_id: str, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.model_id = model_id

    def run(self):
        try:
            self.done.emit(self.manager.activate(self.model_id))
        except Exception as exc:
            self.error.emit(str(exc))


class InstallerWorker(QThread):
    progress = Signal(int, int, str)
    done = Signal(str)
    error = Signal(str)

    def __init__(self, manager: OllamaManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.cancelled = False

    def run(self):
        try:
            path = self.manager.download_installer(
                progress=lambda i, total, text: self.progress.emit(i, total, text),
                cancelled=lambda: self.cancelled,
            )
            self.done.emit(str(path))
        except Exception as exc:
            self.error.emit(str(exc))


class SettingsPage(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.manager = ctx.local_ai or OllamaManager(ctx.settings)
        self._status: dict = {}
        self._status_worker: LocalAIStatusWorker | None = None
        self._pull_worker: ModelPullWorker | None = None
        self._activate_worker: ModelActivateWorker | None = None
        self._installer_worker: InstallerWorker | None = None
        self._model_widgets: dict[str, dict] = {}
        self._build()
        self.load()

    # ------------------------------------------------------------------ UI
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        self.layout_body = QVBoxLayout(body)
        self.layout_body.setContentsMargins(34, 28, 34, 34)
        self.layout_body.setSpacing(16)
        scroll.setWidget(body)
        root.addWidget(scroll)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Настройки")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Локальный ИИ, разрешения, голос, медиа и LAN-сервер. Ключи облачных API не нужны."
        )
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)
        self.version_label = QLabel(f"v{APP_VERSION}")
        self.version_label.setObjectName("Chip")
        header.addWidget(self.version_label)
        self.layout_body.addLayout(header)

        self.layout_body.addWidget(self._build_ai_section())
        self.layout_body.addWidget(self._build_access_section())
        self.layout_body.addWidget(self._build_voice_section())
        self.layout_body.addWidget(self._build_media_section())
        self.layout_body.addWidget(self._build_ui_section())
        self.layout_body.addWidget(self._build_server_section())
        self.layout_body.addWidget(self._build_about_section())

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.save_btn = QPushButton("Сохранить настройки")
        self.save_btn.setObjectName("Accent")
        self.save_btn.clicked.connect(lambda: self.save(show_message=True))
        footer.addWidget(self.save_btn)
        self.layout_body.addLayout(footer)
        self.layout_body.addStretch(1)

    def _section(self, title: str, description: str = "") -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("SettingsCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(11)
        heading = QLabel(title)
        heading.setObjectName("SectionTitle")
        layout.addWidget(heading)
        if description:
            note = QLabel(description)
            note.setObjectName("Muted")
            note.setWordWrap(True)
            layout.addWidget(note)
        return card, layout

    def _build_ai_section(self) -> QFrame:
        card, layout = self._section(
            "Локальный ИИ · Ollama",
            "Две модели. Активна ровно одна: при переключении вторая выгружается из памяти "
            "(keep_alive=0) и новая прогревается. Интернет нужен только для скачивания.",
        )
        service = QFrame()
        service.setObjectName("SoftCard")
        service_layout = QVBoxLayout(service)
        service_layout.setContentsMargins(14, 12, 14, 12)
        service_layout.setSpacing(7)
        row = QHBoxLayout()
        self.ollama_state = QLabel("Проверяю Ollama…")
        self.ollama_state.setStyleSheet("font-weight:650;")
        row.addWidget(self.ollama_state, 1)
        self.ollama_version = QLabel("")
        self.ollama_version.setObjectName("Tiny")
        row.addWidget(self.ollama_version)
        service_layout.addLayout(row)
        self.ollama_path = QLabel("")
        self.ollama_path.setObjectName("Tiny")
        self.ollama_path.setWordWrap(True)
        service_layout.addWidget(self.ollama_path)
        buttons = QHBoxLayout()
        refresh = QPushButton("Проверить снова")
        refresh.setObjectName("Ghost")
        refresh.clicked.connect(self.refresh_ai_status)
        start = QPushButton("Запустить Ollama")
        start.clicked.connect(self.start_ollama)
        installer = QPushButton("Скачать установщик Ollama…")
        installer.setObjectName("Ghost")
        installer.clicked.connect(self.download_ollama)
        buttons.addWidget(refresh)
        buttons.addWidget(start)
        buttons.addWidget(installer)
        buttons.addStretch(1)
        service_layout.addLayout(buttons)
        layout.addWidget(service)

        grid = QGridLayout()
        grid.setSpacing(12)
        for index, info in enumerate(MANAGED_MODELS):
            grid.addWidget(self._build_model_card(info), 0, index)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        self.ai_progress = QProgressBar()
        self.ai_progress.setRange(0, 1000)
        self.ai_progress.setValue(0)
        self.ai_progress.setVisible(False)
        layout.addWidget(self.ai_progress)
        self.ai_progress_text = QLabel("")
        self.ai_progress_text.setObjectName("Tiny")
        self.ai_progress_text.setWordWrap(True)
        layout.addWidget(self.ai_progress_text)

        secrets_row = QHBoxLayout()
        self.secrets_state = QLabel("")
        self.secrets_state.setObjectName("Tiny")
        self.secrets_state.setWordWrap(True)
        secrets_row.addWidget(self.secrets_state, 1)
        purge = QPushButton("Удалить старые API-ключи")
        purge.setObjectName("DangerGhost")
        purge.clicked.connect(self.purge_secrets)
        secrets_row.addWidget(purge)
        layout.addLayout(secrets_row)
        return card

    def _build_model_card(self, info: dict) -> QFrame:
        card = QFrame()
        card.setObjectName("SoftCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 14, 15, 14)
        layout.setSpacing(7)
        top = QHBoxLayout()
        name = QLabel(info["name"])
        name.setStyleSheet("font-size:15px; font-weight:700;")
        top.addWidget(name, 1)
        badge = QLabel(info.get("tag", ""))
        badge.setObjectName("Chip")
        top.addWidget(badge)
        layout.addLayout(top)
        description = QLabel(info.get("description", ""))
        description.setObjectName("Muted")
        description.setWordWrap(True)
        layout.addWidget(description)
        meta = QLabel(
            f"{info.get('size', '')} · {info.get('license', '')} · "
            + ("tool calling" if info.get("tools") else "текст")
        )
        meta.setObjectName("Tiny")
        layout.addWidget(meta)
        state = QLabel("не проверено")
        state.setObjectName("Tiny")
        layout.addWidget(state)
        row = QHBoxLayout()
        download = QPushButton("Скачать")
        download.clicked.connect(lambda _=False, mid=info["id"]: self.pull_model(mid))
        activate = QPushButton("Активировать")
        activate.setObjectName("Accent")
        activate.clicked.connect(lambda _=False, mid=info["id"]: self.activate_model(mid))
        row.addWidget(download)
        row.addWidget(activate)
        row.addStretch(1)
        layout.addLayout(row)
        self._model_widgets[info["id"]] = {
            "state": state, "download": download, "activate": activate,
        }
        return card

    def _build_access_section(self) -> QFrame:
        card, layout = self._section(
            "Доступ ИИ к компьютеру",
            "По умолчанию разрешены только рабочая папка AURA и чтение. Каждое опасное "
            "действие дополнительно подтверждается диалогом. Полный доступ к ПК — это "
            "осознанное разрешение, а не скрытая функция.",
        )
        self.allow_write = QCheckBox("Запись и изменение файлов в разрешённых папках")
        self.allow_shell = QCheckBox("Терминал и запуск команд (с подтверждением)")
        self.allow_network = QCheckBox("Сеть и публичные OSINT-запросы")
        self.allow_system = QCheckBox(
            "Управление Windows: открыть приложение, громкость, скриншот, блокировка, питание"
        )
        for checkbox in (self.allow_write, self.allow_shell, self.allow_network, self.allow_system):
            layout.addWidget(checkbox)
        layout.addWidget(self._hint(
            "Даже при включённых правах AURA спрашивает подтверждение перед записью, "
            "командой, запуском приложения, питанием и OSINT-запросом. Логи есть в %APPDATA%."
        ))
        roots_row = QHBoxLayout()
        roots_col = QVBoxLayout()
        roots_col.addWidget(QLabel("Разрешённые папки"))
        self.roots_list = QListWidget()
        self.roots_list.setMaximumHeight(118)
        roots_col.addWidget(self.roots_list)
        roots_row.addLayout(roots_col, 1)
        buttons = QVBoxLayout()
        add = QPushButton("＋ Добавить")
        add.clicked.connect(self.add_root)
        remove = QPushButton("Убрать")
        remove.setObjectName("Ghost")
        remove.clicked.connect(self.remove_root)
        open_ws = QPushButton("Рабочая папка")
        open_ws.setObjectName("Ghost")
        open_ws.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(DATA_DIR / "workspace"))))
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addWidget(open_ws)
        buttons.addStretch(1)
        roots_row.addLayout(buttons)
        layout.addLayout(roots_row)
        return card

    def _build_voice_section(self) -> QFrame:
        card, layout = self._section(
            "Голос и речь",
            "Распознавание Vosk работает офлайн. Озвучка использует установленные голоса "
            "Windows SAPI. Микрофон включается только кнопкой или Ctrl+Alt+Space.",
        )
        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(9)
        form.addWidget(QLabel("Голос Windows"), 0, 0)
        self.voice_combo = QComboBox()
        self.voice_combo.setMinimumWidth(330)
        form.addWidget(self.voice_combo, 0, 1, 1, 2)
        form.addWidget(QLabel("Скорость"), 1, 0)
        self.voice_rate = QSpinBox()
        self.voice_rate.setRange(80, 320)
        self.voice_rate.setSuffix(" слов/мин")
        form.addWidget(self.voice_rate, 1, 1)
        form.addWidget(QLabel("Громкость"), 2, 0)
        self.voice_volume = QDoubleSpinBox()
        self.voice_volume.setRange(0.0, 1.0)
        self.voice_volume.setSingleStep(0.05)
        form.addWidget(self.voice_volume, 2, 1)
        form.addWidget(QLabel("Глобальная клавиша"), 3, 0)
        self.hotkey_edit = QLineEdit()
        self.hotkey_edit.setPlaceholderText("Ctrl+Alt+Space")
        form.addWidget(self.hotkey_edit, 3, 1)
        self.voice_autospeak = QCheckBox("Озвучивать ответы ИИ автоматически")
        form.addWidget(self.voice_autospeak, 4, 0, 1, 2)
        layout.addLayout(form)
        row = QHBoxLayout()
        test = QPushButton("Проверить голос")
        test.clicked.connect(self.test_voice)
        stop = QPushButton("Стоп")
        stop.setObjectName("Ghost")
        stop.clicked.connect(lambda: self.ctx.tts.stop() if self.ctx.tts else None)
        open_voice = QPushButton("Открыть страницу «Голос»")
        open_voice.setObjectName("Ghost")
        open_voice.clicked.connect(lambda: self.ctx.events.navigate.emit("voice"))
        row.addWidget(test)
        row.addWidget(stop)
        row.addStretch(1)
        row.addWidget(open_voice)
        layout.addLayout(row)
        self.voice_status = QLabel(
            "Модель Vosk: установлена" if self._vosk_ready() else
            "Модель Vosk не установлена — скачайте её на странице «Голос»."
        )
        self.voice_status.setObjectName("Tiny")
        self.voice_status.setWordWrap(True)
        layout.addWidget(self.voice_status)
        return card

    def _build_media_section(self) -> QFrame:
        card, layout = self._section(
            "Медиа-студия",
            "Изображения — через бесплатный keyless-сервис Pollinations (лимит около "
            "1 изображения / 45 секунд). Презентации собираются локально в PPTX, видео — "
            "локально через ffmpeg; при недоступности сети кадры рисуются локально.",
        )
        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(9)
        form.addWidget(QLabel("Модель изображений"), 0, 0)
        self.image_model = QComboBox()
        self.image_model.addItem("auto · стабильный выбор", "auto")
        self.image_model.addItem("turbo · быстрее", "turbo")
        self.image_model.addItem("flux · выше качество", "flux")
        form.addWidget(self.image_model, 0, 1)
        form.addWidget(QLabel("Формат изображения"), 1, 0)
        self.aspect = QComboBox()
        for label, value, w, h in (
            ("1:1 · квадрат", "1:1", 1024, 1024),
            ("16:9 · широкий", "16:9", 1280, 720),
            ("9:16 · вертикальный", "9:16", 720, 1280),
            ("4:3 · презентация", "4:3", 1024, 768),
        ):
            self.aspect.addItem(label, (value, w, h))
        form.addWidget(self.aspect, 1, 1)
        form.addWidget(QLabel("Видео"), 2, 0)
        video_row = QHBoxLayout()
        self.video_width = QSpinBox()
        self.video_width.setRange(480, 1920)
        self.video_width.setSingleStep(80)
        self.video_height = QSpinBox()
        self.video_height.setRange(270, 1080)
        self.video_height.setSingleStep(80)
        video_row.addWidget(self.video_width)
        video_row.addWidget(QLabel("×"))
        video_row.addWidget(self.video_height)
        form.addLayout(video_row, 2, 1)
        self.with_narration = QCheckBox("Озвучивать видео голосом Windows")
        self.with_music = QCheckBox("Добавлять музыку AURA в видео")
        form.addWidget(self.with_narration, 3, 0, 1, 2)
        form.addWidget(self.with_music, 4, 0, 1, 2)
        layout.addLayout(form)
        open_folder = QPushButton("Открыть папку результатов")
        open_folder.setObjectName("Ghost")
        open_folder.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(GENERATED_DIR)))
        )
        layout.addWidget(open_folder, alignment=Qt.AlignmentFlag.AlignLeft)
        return card

    def _build_ui_section(self) -> QFrame:
        card, layout = self._section(
            "Интерфейс",
            "Тема применяется сразу. Язык переключает меню, вход, рабочее пространство и "
            "новые диалоги; содержимое старых страниц пока остаётся на русском.",
        )
        row = QHBoxLayout()
        row.addWidget(QLabel("Тема"))
        self.accent_combo = QComboBox()
        for key, palette in PALETTES.items():
            self.accent_combo.addItem(f"{palette['name']} · {palette['description']}", key)
        self.accent_combo.currentIndexChanged.connect(self.preview_accent)
        row.addWidget(self.accent_combo, 1)
        row.addSpacing(12)
        row.addWidget(QLabel("Язык"))
        self.language_combo = QComboBox()
        for key, name in LANGUAGES.items():
            self.language_combo.addItem(name, key)
        self.language_combo.currentIndexChanged.connect(self.preview_language)
        row.addWidget(self.language_combo)
        row.addStretch(1)
        layout.addLayout(row)
        self.animations = QCheckBox("Плавные переходы и анимация обложки")
        layout.addWidget(self.animations)
        return card

    def _build_server_section(self) -> QFrame:
        card, layout = self._section(
            "Локальный сервер и Android",
            "Сервер отдаёт медиатеку и чат в локальную сеть. Android APK подключается по "
            "адресу и токену. Токен — не API-ключ, он защищает только LAN-доступ.",
        )
        row = QHBoxLayout()
        row.addWidget(QLabel("Порт"))
        self.server_port = QSpinBox()
        self.server_port.setRange(8000, 65535)
        row.addWidget(self.server_port)
        self.server_lan = QCheckBox("Разрешить устройства LAN")
        row.addWidget(self.server_lan)
        self.server_autostart = QCheckBox("Запускать при старте")
        row.addWidget(self.server_autostart)
        self.server_start = QPushButton("Запустить")
        self.server_start.setObjectName("Accent")
        self.server_start.clicked.connect(self.toggle_server)
        row.addWidget(self.server_start)
        row.addStretch(1)
        layout.addLayout(row)
        self.server_state = QLabel("")
        self.server_state.setObjectName("Tiny")
        self.server_state.setWordWrap(True)
        layout.addWidget(self.server_state)
        token_row = QHBoxLayout()
        token_row.addWidget(QLabel("LAN-токен"))
        self.server_token = QLineEdit()
        self.server_token.setReadOnly(True)
        self.server_token.setEchoMode(QLineEdit.EchoMode.Password)
        token_row.addWidget(self.server_token, 1)
        reveal = QPushButton("Показать")
        reveal.setObjectName("Ghost")
        reveal.clicked.connect(self.toggle_token)
        copy = QPushButton("Копировать")
        copy.setObjectName("Ghost")
        copy.clicked.connect(self.copy_token)
        token_row.addWidget(reveal)
        token_row.addWidget(copy)
        layout.addLayout(token_row)
        return card

    def _build_about_section(self) -> QFrame:
        card, layout = self._section("О приложении")
        text = QLabel(
            "AURA Studio — локальный музыкальный плеер, ИИ-ассистент, исследования и "
            "медиа-студия в одном приложении.\n"
            "Никакие API-ключи не требуются. Публичные OSINT-запросы и Pollinations "
            "используют интернет; музыка, речь, ИИ и презентации работают локально.\n"
            "Правовые ограничения: только открытые данные; управление ПК — с подтверждением; "
            "неофициальные API Spotify/Яндекс Музыки не используются."
        )
        text.setObjectName("Muted")
        text.setWordWrap(True)
        layout.addWidget(text)
        open_data = QPushButton("Открыть папку данных")
        open_data.setObjectName("Ghost")
        open_data.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(DATA_DIR))))
        layout.addWidget(open_data, alignment=Qt.AlignmentFlag.AlignLeft)
        return card

    @staticmethod
    def _hint(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("Tiny")
        label.setWordWrap(True)
        return label

    # --------------------------------------------------------------- state
    def load(self):
        s = self.ctx.settings
        self.allow_write.setChecked(bool(s.get("access.allow_write", False)))
        self.allow_shell.setChecked(bool(s.get("access.allow_shell", False)))
        self.allow_network.setChecked(bool(s.get("access.allow_network", True)))
        self.allow_system.setChecked(bool(s.get("access.allow_system", False)))
        self.roots_list.clear()
        for root in s.access_roots():
            item = QListWidgetItem(str(root))
            item.setData(Qt.ItemDataRole.UserRole, str(root))
            self.roots_list.addItem(item)

        self.voice_rate.setValue(int(s.get("voice.rate", 175) or 175))
        self.voice_volume.setValue(float(s.get("voice.volume", 1.0) or 1.0))
        self.hotkey_edit.setText(str(s.get("voice.hotkey", "Ctrl+Alt+Space")))
        self.voice_autospeak.setChecked(bool(s.get("voice.autospeak", False)))
        self._load_voices()

        self.image_model.setCurrentIndex(max(0, self.image_model.findData(str(s.get("media.image_model", "auto")))))
        aspect = str(s.get("media.aspect", "1:1"))
        index = next((i for i in range(self.aspect.count()) if self.aspect.itemData(i)[0] == aspect), 0)
        self.aspect.setCurrentIndex(index)
        self.video_width.setValue(int(s.get("media.video_width", 1280) or 1280))
        self.video_height.setValue(int(s.get("media.video_height", 720) or 720))
        self.with_narration.setChecked(bool(s.get("media.with_narration", True)))
        self.with_music.setChecked(bool(s.get("media.with_music", True)))

        accent = str(s.get("ui.accent", "sunset"))
        idx = self.accent_combo.findData(accent)
        self.accent_combo.blockSignals(True)
        self.accent_combo.setCurrentIndex(max(0, idx))
        self.accent_combo.blockSignals(False)
        language = str(s.get("ui.language", "ru"))
        self.language_combo.blockSignals(True)
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(language)))
        self.language_combo.blockSignals(False)
        self.animations.setChecked(bool(s.get("ui.animations", True)))

        self.server_port.setValue(int(s.get("server.port", 8765) or 8765))
        self.server_lan.setChecked(bool(s.get("server.lan", False)))
        self.server_autostart.setChecked(bool(s.get("server.autostart", False)))
        self.server_token.setText(s.secret("server_token"))
        self._refresh_server_state()
        self._refresh_secrets_count()
        self.refresh_ai_status()

    def _load_voices(self):
        current = str(self.ctx.settings.get("voice.voice_name", ""))
        self.voice_combo.clear()
        voices = self.ctx.tts.voices() if self.ctx.tts else []
        if not voices:
            self.voice_combo.addItem("Windows SAPI недоступен", "")
            return
        for voice in voices:
            self.voice_combo.addItem(voice["name"], voice["id"])
        selected = 0
        if current:
            for index in range(self.voice_combo.count()):
                data = str(self.voice_combo.itemData(index) or "")
                text = self.voice_combo.itemText(index)
                if current == data or current.lower() in text.lower():
                    selected = index
                    break
        elif self.ctx.tts:
            preferred = self.ctx.tts.preferred_voice_id()
            for index in range(self.voice_combo.count()):
                if self.voice_combo.itemData(index) == preferred:
                    selected = index
                    break
        self.voice_combo.setCurrentIndex(selected)

    def _refresh_server_state(self):
        server = self.ctx.server
        if server.running:
            self.server_start.setText("Остановить")
            self.server_state.setText(
                f"● Работает: {server.url()} · LAN: {server.lan_url() or 'выключен'}"
            )
        else:
            self.server_start.setText("Запустить")
            self.server_state.setText("○ Сервер остановлен")

    def _refresh_secrets_count(self):
        count = sum(1 for key in LEGACY_API_SECRETS if key in self.ctx.settings.secrets)
        if count:
            self.secrets_state.setText(
                f"В зашифрованном хранилище осталось старых секретов: {count}. "
                "Они больше не используются интерфейсом."
            )
        else:
            self.secrets_state.setText(
                "Старых облачных ключей нет. LAN-токен хранится отдельно и нужен Android-клиенту."
            )

    # ------------------------------------------------------------ local AI
    def refresh_ai_status(self):
        if self._status_worker and self._status_worker.isRunning():
            return
        self.ollama_state.setText("Проверяю Ollama…")
        worker = LocalAIStatusWorker(self.manager, self)
        self._status_worker = worker
        worker.done.connect(self._status_ready)
        worker.start()

    def _status_ready(self, status: dict):
        self._status = status or {}
        running = bool(status.get("running"))
        if running:
            self.ollama_state.setText("● Ollama работает на 127.0.0.1:11434")
            self.ollama_state.setStyleSheet("font-weight:650; color:#5bdd9a;")
            self.ollama_version.setText("версия " + str(status.get("version") or "?"))
            exe = str(status.get("executable") or "")
            self.ollama_path.setText("Исполняемый файл: " + exe if exe else "Ollama доступен как сервис")
        else:
            self.ollama_state.setText("○ Ollama не отвечает")
            self.ollama_state.setStyleSheet("font-weight:650; color:#ff9f80;")
            self.ollama_version.setText("")
            self.ollama_path.setText(str(status.get("error") or "Запустите сервис или скачайте установщик."))
        installed = {str(item.get("id", "")): item for item in status.get("installed") or []}
        for info in MANAGED_MODELS:
            widgets = self._model_widgets[info["id"]]
            normalized = info["id"]
            found = any(
                key == normalized or key.split(":")[0] == normalized.split(":")[0]
                for key in installed
            )
            is_active = str(status.get("active") or "").split(":")[0] == normalized.split(":")[0]
            if found:
                size = next(
                    (int(row.get("size") or 0) for key, row in installed.items()
                     if key.split(":")[0] == normalized.split(":")[0]),
                    0,
                )
                label = "скачана" + (f" · {self._human(size)}" if size else "")
                widgets["download"].setText("Скачана")
                widgets["download"].setEnabled(False)
                widgets["activate"].setEnabled(not is_active)
                widgets["activate"].setText("Активна" if is_active else "Активировать")
                widgets["state"].setText(("● активна" if is_active else "○ готова") + f" · {label}")
                if is_active:
                    widgets["state"].setStyleSheet("color:#5bdd9a; font-weight:600;")
                else:
                    widgets["state"].setStyleSheet("")
            else:
                widgets["download"].setText("Скачать")
                widgets["download"].setEnabled(running)
                widgets["activate"].setText("Активировать")
                widgets["activate"].setEnabled(False)
                widgets["state"].setText("○ не скачана")
                widgets["state"].setStyleSheet("")

    @staticmethod
    def _human(value: int) -> str:
        value = float(value or 0)
        for unit in ("Б", "КБ", "МБ", "ГБ"):
            if value < 1024 or unit == "ГБ":
                return f"{value:.1f} {unit}" if value >= 10 else f"{value:.2f} {unit}"
            value /= 1024
        return f"{value:.1f} ГБ"

    def start_ollama(self):
        self.ollama_state.setText("Запускаю Ollama…")
        QApplication.processEvents()
        try:
            result = self.manager.ensure_running()
            self.ctx.events.toast.emit(
                "Ollama запущен" + (" заново." if result.get("started") else " (уже работал).")
            )
        except LocalAIError as exc:
            QMessageBox.warning(self, "Ollama", str(exc))
        except Exception as exc:
            QMessageBox.warning(self, "Ollama", f"Не удалось запустить Ollama:\n{exc}")
        self.refresh_ai_status()

    def download_ollama(self):
        if self._installer_worker and self._installer_worker.isRunning():
            return
        if QMessageBox.question(
            self, "Ollama",
            "Будет скачан официальный установщик Ollama (около 1.6 ГБ) с GitHub, "
            "затем откроется установка. Продолжить?",
        ) != QMessageBox.StandardButton.Yes:
            return
        worker = InstallerWorker(self.manager, self)
        self._installer_worker = worker
        self.ai_progress.setVisible(True)
        self.ai_progress.setValue(0)
        self.ai_progress_text.setText("Скачиваю установщик Ollama…")
        worker.progress.connect(self._pull_progress)
        worker.done.connect(self._installer_done)
        worker.error.connect(self._worker_error)
        worker.start()

    def _installer_done(self, path: str):
        self.ai_progress.setVisible(False)
        self.ai_progress_text.setText(f"Установщик готов: {path}")
        try:
            self.manager.launch_installer()
            QMessageBox.information(
                self, "Ollama",
                "Установщик открыт. Завершите установку, затем вернитесь в AURA и нажмите "
                "«Проверить снова».",
            )
        except Exception as exc:
            QMessageBox.warning(self, "Ollama", f"Установщик скачан, но не открылся:\n{exc}\n\n{path}")

    def pull_model(self, model_id: str):
        if self._pull_worker and self._pull_worker.isRunning():
            self.ctx.events.toast.emit("Другая модель уже скачивается.")
            return
        if not self.manager.running():
            self.start_ollama()
        if not self.manager.running():
            QMessageBox.warning(self, "Модель", "Сначала запустите Ollama.")
            return
        info = model_info(model_id)
        worker = ModelPullWorker(self.manager, model_id, self)
        self._pull_worker = worker
        self.ai_progress.setVisible(True)
        self.ai_progress.setValue(0)
        self.ai_progress_text.setText(f"Скачиваю {info['name'] if info else model_id}…")
        for widgets in self._model_widgets.values():
            widgets["download"].setEnabled(False)
            widgets["activate"].setEnabled(False)
        worker.progress.connect(self._pull_progress)
        worker.done.connect(self._pull_done)
        worker.error.connect(self._worker_error)
        worker.start()

    def _pull_progress(self, done: int, total: int, text: str):
        if total > 0:
            self.ai_progress.setRange(0, 1000)
            self.ai_progress.setValue(min(1000, int(done * 1000 / total)))
        else:
            self.ai_progress.setRange(0, 0)
        self.ai_progress_text.setText(
            f"{text} · {self._human(done)}" + (f" / {self._human(total)}" if total else "")
        )

    def _pull_done(self, result: dict):
        self.ai_progress.setVisible(False)
        self.ai_progress_text.setText("Модель готова к активации.")
        self.ctx.events.toast.emit("Модель скачана. Активируйте её.")
        self.refresh_ai_status()

    def _worker_error(self, message: str):
        self.ai_progress.setVisible(False)
        self.ai_progress_text.setText("Ошибка: " + message)
        QMessageBox.warning(self, "AURA · Локальный ИИ", message)
        self.refresh_ai_status()

    def activate_model(self, model_id: str):
        if self._activate_worker and self._activate_worker.isRunning():
            return
        worker = ModelActivateWorker(self.manager, model_id, self)
        self._activate_worker = worker
        self.ai_progress.setVisible(True)
        self.ai_progress.setRange(0, 0)
        info = model_info(model_id)
        self.ai_progress_text.setText(
            f"Переключаюсь на {info['name'] if info else model_id}: выгружаю вторую модель и прогреваю выбранную…"
        )
        for widgets in self._model_widgets.values():
            widgets["activate"].setEnabled(False)
        worker.done.connect(self._activate_done)
        worker.error.connect(self._worker_error)
        worker.start()

    def _activate_done(self, result: dict):
        self.ai_progress.setVisible(False)
        self.ai_progress.setRange(0, 1000)
        self.ctx.events.settings_changed.emit()
        self.ctx.events.toast.emit(
            "Активна модель " + str(result.get("active"))
            + (". Вторая выгружена." if result.get("unloaded") else ".")
        )
        self.refresh_ai_status()

    def purge_secrets(self):
        count = sum(1 for key in LEGACY_API_SECRETS if key in self.ctx.settings.secrets)
        if not count:
            QMessageBox.information(self, "Секреты", "Старых облачных ключей нет.")
            return
        if QMessageBox.question(
            self, "Удалить старые ключи",
            f"Безвозвратно удалить {count} старых облачных/OAuth секретов из зашифрованного "
            "хранилища?\n\nLAN-токен останется: он нужен Android-клиенту.",
        ) != QMessageBox.StandardButton.Yes:
            return
        removed = self.ctx.settings.purge_legacy_secrets()
        self._refresh_secrets_count()
        self.ctx.events.toast.emit(f"Удалено секретов: {len(removed)}")

    # --------------------------------------------------------------- access
    def add_root(self):
        folder = QFileDialog.getExistingDirectory(self, "Разрешить папку для ИИ")
        if not folder:
            return
        for index in range(self.roots_list.count()):
            if self.roots_list.item(index).text() == folder:
                return
        item = QListWidgetItem(folder)
        item.setData(Qt.ItemDataRole.UserRole, folder)
        self.roots_list.addItem(item)

    def remove_root(self):
        item = self.roots_list.currentItem()
        if item is not None:
            self.roots_list.takeItem(self.roots_list.row(item))

    # ---------------------------------------------------------------- voice
    def test_voice(self):
        if not self.ctx.tts:
            QMessageBox.warning(self, "Голос", "TTS-сервис недоступен.")
            return
        self._save_voice_preview()
        self.ctx.tts.speak(
            "Привет! Это AURA Studio. Локальная озвучка Windows работает. "
            "Голосовой ввод использует офлайн-модель Vosk."
        )
        self.voice_status.setText("Произношу тестовую фразу…")

    def _save_voice_preview(self):
        s = self.ctx.settings
        s.set("voice.voice_name", str(self.voice_combo.currentData() or ""))
        s.set("voice.rate", int(self.voice_rate.value()))
        s.set("voice.volume", float(self.voice_volume.value()))
        s.set("voice.autospeak", bool(self.voice_autospeak.isChecked()))
        s.set("voice.hotkey", self.hotkey_edit.text().strip() or "Ctrl+Alt+Space")
        s.save()

    @staticmethod
    def _vosk_ready() -> bool:
        try:
            from core.voice import vosk_installed
            return vosk_installed()
        except Exception:
            return False

    # ----------------------------------------------------------------- theme
    def preview_accent(self):
        accent = str(self.accent_combo.currentData() or "sunset")
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, accent)
        self.ctx.events.accent_changed.emit(accent)

    def preview_language(self):
        language = str(self.language_combo.currentData() or "ru")
        self.ctx.settings.set("ui.language", language)
        self.ctx.settings.save()
        self.ctx.events.settings_changed.emit()

    # ---------------------------------------------------------------- server
    def toggle_server(self):
        if self.ctx.server.running:
            self.ctx.server.stop()
        else:
            try:
                result = self.ctx.server.start(
                    int(self.server_port.value()), bool(self.server_lan.isChecked())
                )
                if not result.get("ok"):
                    QMessageBox.warning(self, "Сервер", str(result.get("error") or "не запустился"))
            except Exception as exc:
                QMessageBox.warning(self, "Сервер", str(exc))
        self._refresh_server_state()
        self.ctx.events.settings_changed.emit()

    def toggle_token(self):
        if self.server_token.echoMode() == QLineEdit.EchoMode.Password:
            self.server_token.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.server_token.setEchoMode(QLineEdit.EchoMode.Password)

    def copy_token(self):
        QApplication.clipboard().setText(self.server_token.text())
        self.ctx.events.toast.emit("LAN-токен скопирован.")

    # ------------------------------------------------------------------ save
    def save(self, show_message: bool = False):
        s = self.ctx.settings
        s.set("access.allow_write", bool(self.allow_write.isChecked()))
        s.set("access.allow_shell", bool(self.allow_shell.isChecked()))
        s.set("access.allow_network", bool(self.allow_network.isChecked()))
        s.set("access.allow_system", bool(self.allow_system.isChecked()))
        roots = [
            str(self.roots_list.item(i).data(Qt.ItemDataRole.UserRole) or self.roots_list.item(i).text())
            for i in range(self.roots_list.count())
        ]
        s.set("access.roots", roots)
        self._save_voice_preview()
        aspect_data = self.aspect.currentData() or ("1:1", 1024, 1024)
        s.set("media.aspect", aspect_data[0])
        s.set("media.width", int(aspect_data[1]))
        s.set("media.height", int(aspect_data[2]))
        s.set("media.image_model", str(self.image_model.currentData() or "auto"))
        s.set("media.video_width", int(self.video_width.value()))
        s.set("media.video_height", int(self.video_height.value()))
        s.set("media.with_narration", bool(self.with_narration.isChecked()))
        s.set("media.with_music", bool(self.with_music.isChecked()))
        s.set("ui.accent", str(self.accent_combo.currentData() or "sunset"))
        s.set("ui.language", str(self.language_combo.currentData() or "ru"))
        s.set("ui.animations", bool(self.animations.isChecked()))
        s.set("server.port", int(self.server_port.value()))
        s.set("server.lan", bool(self.server_lan.isChecked()))
        s.set("server.autostart", bool(self.server_autostart.isChecked()))
        s.save()
        self.ctx.tools.refresh()
        self.ctx.events.settings_changed.emit()
        self.ctx.events.accent_changed.emit(str(s.get("ui.accent", "sunset")))
        if show_message:
            self.ctx.events.toast.emit("Настройки сохранены.")
            QMessageBox.information(
                self, "AURA",
                "Настройки сохранены. Права доступа и голос применены. "
                "Глобальная клавиша перерегистрируется автоматически.",
            )

    def shutdown(self):
        for worker in (self._status_worker, self._pull_worker, self._activate_worker, self._installer_worker):
            if worker is None:
                continue
            if isinstance(worker, (ModelPullWorker, InstallerWorker)):
                worker.cancelled = True
            if worker.isRunning():
                worker.wait(2500)
