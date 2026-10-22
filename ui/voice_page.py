"""Voice page: offline Vosk recognition, command router and Windows TTS."""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSpinBox,
    QTextBrowser, QVBoxLayout, QWidget,
)

from core.voice import (
    COMMAND_HELP, VOSK_MODEL_SIZE, download_vosk_model, vosk_installed,
    vosk_model_path,
)
from ui.context import AppContext


class VoskDownloadWorker(QThread):
    progress = Signal(int, int, str)
    done = Signal(str)
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cancelled = False

    def run(self):
        try:
            path = download_vosk_model(
                progress=lambda i, total, text: self.progress.emit(i, total, text),
                cancelled=lambda: self.cancelled,
            )
            self.done.emit(str(path))
        except Exception as exc:
            self.error.emit(str(exc))


class ListenWorker(QThread):
    partial = Signal(str)
    done = Signal(str)
    error = Signal(str)

    def __init__(self, recognizer, parent=None):
        super().__init__(parent)
        self.recognizer = recognizer
        self.cancelled = False

    def run(self):
        try:
            text = self.recognizer.listen(
                max_seconds=9.0,
                on_partial=lambda value: self.partial.emit(value),
                cancelled=lambda: self.cancelled,
            )
            self.done.emit(text)
        except Exception as exc:
            self.error.emit(str(exc))


class CommandWorker(QThread):
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, router, text: str, approve, parent=None):
        super().__init__(parent)
        self.router = router
        self.text = text
        self.approve = approve

    def run(self):
        try:
            self.done.emit(self.router.execute(self.text, approve=self.approve))
        except Exception as exc:
            self.error.emit(str(exc))


class VoicePage(QWidget):
    def __init__(self, ctx: AppContext, approve, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.approve = approve
        self._vosk_worker: VoskDownloadWorker | None = None
        self._listen_worker: ListenWorker | None = None
        self._command_worker: CommandWorker | None = None
        self._last_command = ""
        self._build()
        self._refresh_model_state()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(34, 27, 34, 26)
        root.setSpacing(13)
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Голос")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Офлайн-распознавание русской речи, команды приложению и ПК, локальная озвучка Windows."
        )
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)
        self.hotkey_label = QLabel("")
        self.hotkey_label.setObjectName("Chip")
        header.addWidget(self.hotkey_label)
        root.addLayout(header)

        banner = QFrame()
        banner.setObjectName("Banner")
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(14, 10, 14, 10)
        note = QLabel(
            "Микрофон включается только вручную или глобальной клавишей. Аудио не "
            "отправляется в интернет. Опасные команды ПК требуют включённого доступа и "
            "подтверждения в диалоге. AURA не выполняет скрытый «полный контроль»."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        banner_layout.addWidget(note)
        root.addWidget(banner)

        content = QHBoxLayout()
        content.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(12)
        mic_card = QFrame()
        mic_card.setObjectName("Card")
        mic_layout = QVBoxLayout(mic_card)
        mic_layout.setContentsMargins(18, 16, 18, 16)
        mic_layout.setSpacing(10)
        self.listen_btn = QPushButton("◉  Начать слушать")
        self.listen_btn.setObjectName("Accent")
        self.listen_btn.setMinimumHeight(56)
        self.listen_btn.clicked.connect(self.start_listening)
        mic_layout.addWidget(self.listen_btn)
        self.recognized = QLabel("Скажите команду…")
        self.recognized.setObjectName("Muted")
        self.recognized.setWordWrap(True)
        self.recognized.setMinimumHeight(38)
        mic_layout.addWidget(self.recognized)
        self.model_state = QLabel("")
        self.model_state.setObjectName("Tiny")
        self.model_state.setWordWrap(True)
        mic_layout.addWidget(self.model_state)
        self.model_progress = QProgressBar()
        self.model_progress.setRange(0, 1000)
        self.model_progress.setValue(0)
        self.model_progress.setVisible(False)
        mic_layout.addWidget(self.model_progress)
        row = QHBoxLayout()
        self.download_btn = QPushButton("Скачать модель Vosk")
        self.download_btn.clicked.connect(self.download_model)
        self.repeat_btn = QPushButton("Повторить команду")
        self.repeat_btn.setObjectName("Ghost")
        self.repeat_btn.clicked.connect(self.repeat_command)
        row.addWidget(self.download_btn)
        row.addWidget(self.repeat_btn)
        row.addStretch(1)
        mic_layout.addLayout(row)
        self.auto_run = QCheckBox("Выполнять распознанную команду сразу")
        self.auto_run.setChecked(True)
        mic_layout.addWidget(self.auto_run)
        self.speak_result = QCheckBox("Озвучивать ответ AURA")
        self.speak_result.setChecked(True)
        mic_layout.addWidget(self.speak_result)
        left.addWidget(mic_card)

        tts_card = QFrame()
        tts_card.setObjectName("Card")
        tts_layout = QVBoxLayout(tts_card)
        tts_layout.setContentsMargins(18, 16, 18, 16)
        tts_layout.setSpacing(9)
        tts_title = QLabel("Озвучка Windows SAPI")
        tts_title.setObjectName("SectionTitle")
        tts_layout.addWidget(tts_title)
        self.voice_combo = QComboBox()
        tts_layout.addWidget(self.voice_combo)
        row = QHBoxLayout()
        tts_layout.addWidget(QLabel("Скорость"))
        self.rate = QSpinBox()
        self.rate.setRange(80, 320)
        self.rate.setSuffix(" слов/мин")
        row.addWidget(self.rate, 1)
        tts_layout.addLayout(row)
        row = QHBoxLayout()
        tts_layout.addWidget(QLabel("Громкость"))
        self.volume = QDoubleSpinBox()
        self.volume.setRange(0.0, 1.0)
        self.volume.setSingleStep(0.05)
        row.addWidget(self.volume, 1)
        tts_layout.addLayout(row)
        test_row = QHBoxLayout()
        test = QPushButton("Проверить голос")
        test.clicked.connect(self.test_voice)
        stop = QPushButton("Стоп")
        stop.setObjectName("Ghost")
        stop.clicked.connect(lambda: self.ctx.tts.stop() if self.ctx.tts else None)
        test_row.addWidget(test)
        test_row.addWidget(stop)
        test_row.addStretch(1)
        tts_layout.addLayout(test_row)
        left.addWidget(tts_card)
        left.addStretch(1)

        right = QVBoxLayout()
        log_card = QFrame()
        log_card.setObjectName("Card")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(16, 14, 16, 14)
        log_layout.setSpacing(8)
        log_header = QHBoxLayout()
        log_title = QLabel("Журнал команд")
        log_title.setObjectName("SectionTitle")
        log_header.addWidget(log_title)
        log_header.addStretch(1)
        clear = QPushButton("Очистить")
        clear.setObjectName("Ghost")
        clear.clicked.connect(lambda: self.log.clear())
        log_header.addWidget(clear)
        log_layout.addLayout(log_header)
        self.log = QTextBrowser()
        self.log.setObjectName("ChatView")
        self.log.setPlainText(
            "Здесь появятся распознанные команды и ответы.\n\n"
            "Нажмите «Начать слушать» или используйте глобальную клавишу.\n"
        )
        log_layout.addWidget(self.log, 1)
        help_card, help_layout = self._help_card()
        log_layout.addWidget(help_card)
        right.addWidget(log_card, 1)
        content.addLayout(left, 2)
        content.addLayout(right, 3)
        root.addLayout(content, 1)

        self._load_voice_controls()

    def _help_card(self) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("SoftCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        title = QLabel("Что можно сказать")
        title.setStyleSheet("font-weight:650;")
        layout.addWidget(title)
        text = QLabel(COMMAND_HELP)
        text.setObjectName("Tiny")
        text.setWordWrap(True)
        layout.addWidget(text)
        return card, layout

    # ----------------------------------------------------------------- state
    def _refresh_model_state(self):
        hotkey = str(self.ctx.settings.get("voice.hotkey", "Ctrl+Alt+Space"))
        self.hotkey_label.setText("Глобальная клавиша · " + hotkey)
        installed = vosk_installed()
        path = vosk_model_path()
        if installed:
            size = sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
            self.model_state.setText(
                f"● Vosk установлен: {path}\n{size / (1024 * 1024):.1f} МБ · распознавание офлайн"
            )
            self.model_state.setStyleSheet("color:#5bdd9a;")
            self.download_btn.setEnabled(False)
            self.download_btn.setText("Модель установлена")
            self.listen_btn.setEnabled(True)
        else:
            self.model_state.setText(
                f"○ Модель Vosk не установлена. Нужно скачать {VOSK_MODEL_SIZE / 1048576:.0f} МБ "
                "из официального репозитория Alphacep (GitHub)."
            )
            self.model_state.setStyleSheet("color:#ffab7d;")
            self.download_btn.setEnabled(True)
            self.download_btn.setText("Скачать модель Vosk")
            self.listen_btn.setEnabled(False)

    def download_model(self):
        if self._vosk_worker and self._vosk_worker.isRunning():
            return
        worker = VoskDownloadWorker(self)
        self._vosk_worker = worker
        self.download_btn.setEnabled(False)
        self.model_progress.setVisible(True)
        self.model_progress.setValue(0)
        self.model_state.setText("Скачиваю русскую модель Vosk…")
        worker.progress.connect(self._download_progress)
        worker.done.connect(self._download_done)
        worker.error.connect(self._download_error)
        worker.start()

    def _download_progress(self, done: int, total: int, text: str):
        if total:
            self.model_progress.setRange(0, 1000)
            self.model_progress.setValue(min(1000, int(done * 1000 / total)))
            self.model_state.setText(
                f"{text} · {done / 1048576:.1f} / {total / 1048576:.1f} МБ"
            )
        else:
            self.model_progress.setRange(0, 0)
            self.model_state.setText(text)

    def _download_done(self, path: str):
        self.model_progress.setVisible(False)
        self.download_btn.setEnabled(False)
        self._refresh_model_state()
        self.ctx.events.toast.emit("Модель Vosk установлена.")
        QMessageBox.information(
            self, "Vosk", "Русская модель распознавания установлена.\n\n" + path
        )

    def _download_error(self, message: str):
        self.model_progress.setVisible(False)
        self.download_btn.setEnabled(True)
        self._refresh_model_state()
        QMessageBox.warning(self, "Vosk", "Не удалось скачать модель:\n\n" + message)

    # ------------------------------------------------------------- listening
    def start_listening(self):
        if self._listen_worker and self._listen_worker.isRunning():
            self._listen_worker.cancelled = True
            self.listen_btn.setText("◉  Остановить")
            return
        if not vosk_installed():
            answer = QMessageBox.question(
                self, "Нужна модель Vosk",
                "Для офлайн-распознавания нужно скачать русскую модель Vosk (~44 МБ) "
                "из официального репозитория Alphacep. Скачать сейчас?",
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.download_model()
            return
        if not self.ctx.recognizer:
            QMessageBox.warning(self, "Голос", "Распознаватель недоступен.")
            return
        worker = ListenWorker(self.ctx.recognizer, self)
        self._listen_worker = worker
        self.listen_btn.setText("●  Слушаю… нажмите, чтобы остановить")
        self.recognized.setText("Говорите…")
        worker.partial.connect(self._partial)
        worker.done.connect(self._heard)
        worker.error.connect(self._listen_error)
        worker.start()

    def _partial(self, text: str):
        self.recognized.setText(text)

    def _heard(self, text: str):
        self.listen_btn.setText("◉  Начать слушать")
        self.recognized.setText(text or "Ничего не расслышала.")
        if not text.strip():
            self._append_log("🎤", "—", "Речь не распознана.")
            return
        self._append_log("🎤", text, "")
        self._last_command = text
        if self.auto_run.isChecked():
            self.execute_command(text)

    def _listen_error(self, message: str):
        self.listen_btn.setText("◉  Начать слушать")
        self.recognized.setText("Ошибка микрофона.")
        self._append_log("⚠", message, "")
        QMessageBox.warning(self, "Голос", message)

    def repeat_command(self):
        if self._last_command:
            self.execute_command(self._last_command)
        else:
            self.recognized.setText("Ещё нет распознанной команды.")

    def execute_command(self, text: str):
        if self._command_worker and self._command_worker.isRunning():
            self._append_log("…", text, "Предыдущая команда ещё выполняется.")
            return
        if not self.ctx.voice_router:
            self._append_log("⚠", text, "Голосовой маршрутизатор не подключён.")
            return
        worker = CommandWorker(self.ctx.voice_router, text, self.approve, self)
        self._command_worker = worker
        self.recognized.setText("Выполняю: " + text)
        worker.done.connect(self._command_done)
        worker.error.connect(lambda message: self._append_log("⚠", text, message))
        worker.start()

    def _command_done(self, result: dict):
        text = str(result.get("text") or "").strip()
        self.recognized.setText(text[:700])
        self._append_log("◉", self._last_command, text)
        if self.speak_result.isChecked() and self.ctx.tts and text:
            self.ctx.tts.speak(text[:1500])

    def _append_log(self, icon: str, command: str, answer: str):
        stamp = time.strftime("%H:%M:%S")
        block = f"[{stamp}] {icon} {command}".strip()
        if answer:
            block += "\n" + answer
        self.log.append(block + "\n")
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    # ------------------------------------------------------------------- TTS
    def _load_voice_controls(self):
        current = str(self.ctx.settings.get("voice.voice_name", ""))
        self.voice_combo.clear()
        voices = self.ctx.tts.voices() if self.ctx.tts else []
        if not voices:
            self.voice_combo.addItem("SAPI-голоса не найдены", "")
        for voice in voices:
            self.voice_combo.addItem(voice["name"], voice["id"])
        if current:
            for index in range(self.voice_combo.count()):
                data = str(self.voice_combo.itemData(index) or "")
                if current == data or current.lower() in self.voice_combo.itemText(index).lower():
                    self.voice_combo.setCurrentIndex(index)
                    break
        self.rate.setValue(int(self.ctx.settings.get("voice.rate", 175) or 175))
        self.volume.setValue(float(self.ctx.settings.get("voice.volume", 1.0) or 1.0))
        self.voice_combo.currentIndexChanged.connect(self._save_tts)
        self.rate.valueChanged.connect(self._save_tts)
        self.volume.valueChanged.connect(self._save_tts)

    def _save_tts(self):
        s = self.ctx.settings
        s.set("voice.voice_name", str(self.voice_combo.currentData() or ""))
        s.set("voice.rate", int(self.rate.value()))
        s.set("voice.volume", float(self.volume.value()))
        s.save()

    def test_voice(self):
        if not self.ctx.tts:
            return
        self._save_tts()
        self.ctx.tts.speak(
            "Привет! Я AURA. Голосовое управление работает локально. "
            "Скажите: открой библиотеку, включи музыку, сделай скриншот или проверь домен example точка com."
        )

    # -------------------------------------------------------------- lifecycle
    def shutdown(self):
        for worker in (self._vosk_worker, self._listen_worker, self._command_worker):
            if worker is None:
                continue
            if isinstance(worker, (VoskDownloadWorker, ListenWorker)):
                worker.cancelled = True
            if worker.isRunning():
                worker.wait(2500)
