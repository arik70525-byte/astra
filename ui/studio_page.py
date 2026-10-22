"""Real media studio: AI images, PPTX presentations, MP4 video and GitHub."""
from __future__ import annotations

import json
import time
from pathlib import Path

from PySide6.QtCore import QThread, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QSpinBox, QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from core import github
from core.media_studio import (
    MediaError, generate_image, generate_presentation, generate_video, output_dir,
)
from ui.context import AppContext


class ImageWorker(QThread):
    progress = Signal(str)
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, prompt: str, width: int, height: int, model: str, parent=None):
        super().__init__(parent)
        self.prompt = prompt
        self.width = width
        self.height = height
        self.model = model

    def run(self):
        try:
            self.done.emit(generate_image(
                self.prompt, width=self.width, height=self.height,
                model=self.model, progress=self.progress.emit,
            ))
        except Exception as exc:
            self.error.emit(str(exc))


class PresentationWorker(QThread):
    progress = Signal(str)
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, ctx, topic, audience, slides, use_ai, with_images, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.topic = topic
        self.audience = audience
        self.slides = slides
        self.use_ai = use_ai
        self.with_images = with_images

    def run(self):
        try:
            self.done.emit(generate_presentation(
                self.topic, audience=self.audience, slides=self.slides,
                use_ai=self.use_ai, ai=self.ctx.ai if self.use_ai else None,
                with_images=self.with_images, progress=self.progress.emit,
            ))
        except Exception as exc:
            self.error.emit(str(exc))


class VideoWorker(QThread):
    progress = Signal(str)
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, ctx, prompt, count, seconds, width, height, use_ai, narration, music):
        super().__init__()
        self.ctx = ctx
        self.prompt = prompt
        self.count = count
        self.seconds = seconds
        self.width = width
        self.height = height
        self.use_ai = use_ai
        self.narration = narration
        self.music = music

    def run(self):
        try:
            self.done.emit(generate_video(
                self.prompt, image_count=self.count, seconds_per_image=self.seconds,
                width=self.width, height=self.height, use_ai_images=self.use_ai,
                narration=self.narration, tts=self.ctx.tts if self.narration else None,
                use_demo_music=self.music, progress=self.progress.emit,
            ))
        except Exception as exc:
            self.error.emit(str(exc))


class GitHubWorker(QThread):
    done = Signal(str)
    error = Signal(str)

    def __init__(self, settings, action: str, value: str = "", parent=None):
        super().__init__(parent)
        self.settings = settings
        self.action = action
        self.value = value

    def run(self):
        try:
            self.done.emit(self._run())
        except Exception as exc:
            self.error.emit(str(exc))

    def _run(self) -> str:
        if self.action == "profile":
            profile = github.public_profile(self.value)
            repos = github.public_repos(self.value, 12)
            lines = [
                f"GitHub · @{profile['login']}",
                "",
                f"Имя: {profile.get('name') or '—'}",
                f"Био: {profile.get('bio') or '—'}",
                f"Компания: {profile.get('company') or '—'}",
                f"Локация: {profile.get('location') or '—'}",
                f"Сайт: {profile.get('blog') or '—'}",
                f"Репозиториев: {profile.get('public_repos')} · подписчиков: {profile.get('followers')}",
                f"Создан: {profile.get('created_at') or '—'}",
                f"Страница: {profile.get('url')}",
                "",
                f"Последние репозитории ({len(repos)}):",
            ]
            for repo in repos:
                lines.append(
                    f"• {repo['name']} · ★ {repo['stars']} · {repo.get('language') or '—'}"
                    + (" · fork" if repo.get("fork") else "")
                )
                if repo.get("description"):
                    lines.append(f"  {repo['description']}")
            return "\n".join(lines)
        if self.action == "search":
            repos = github.search_repositories(self.value, 20)
            if not repos:
                return "Репозитории не найдены."
            lines = [f"GitHub · поиск «{self.value}»", ""]
            for index, repo in enumerate(repos, start=1):
                lines.append(
                    f"{index}. {repo['name']} · ★ {repo['stars']} · {repo.get('language') or '—'}\n"
                    f"   {repo.get('description') or '—'}\n   {repo.get('url')}"
                )
            return "\n".join(lines)
        if self.action == "status":
            status = github.gh_status(self.settings)
            if not status.get("installed"):
                return (
                    "GitHub CLI не установлен.\n\n"
                    "Публичные профили и поиск работают без него. Для приватных репозиториев "
                    "и git push установите официальный GitHub CLI и выполните вход."
                )
            if status.get("authenticated"):
                return (
                    f"GitHub CLI установлен: {status.get('path')}\n"
                    f"Вход выполнен: @{status.get('username') or 'пользователь'}\n\n"
                    "Приватные репозитории и push доступны через gh; токен хранится в "
                    "официальной конфигурации GitHub CLI, не в AURA."
                )
            return (
                f"GitHub CLI установлен: {status.get('path')}\n"
                "Вход не выполнен. Нажмите «Войти через GitHub CLI» — откроется официальный "
                "браузерный вход gh auth login."
            )
        return "Неизвестная операция."


class GhInstallWorker(QThread):
    progress = Signal(int, int, str)
    done = Signal(str)
    error = Signal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.cancelled = False

    def run(self):
        try:
            self.done.emit(github.download_gh_cli(
                self.settings,
                progress=lambda i, total, text: self.progress.emit(i, total, text),
                cancelled=lambda: self.cancelled,
            ))
        except Exception as exc:
            self.error.emit(str(exc))


def _card(title: str, subtitle: str = "") -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("Card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(9)
    heading = QLabel(title)
    heading.setObjectName("SectionTitle")
    layout.addWidget(heading)
    if subtitle:
        note = QLabel(subtitle)
        note.setObjectName("Tiny")
        note.setWordWrap(True)
        layout.addWidget(note)
    return card, layout


class StudioPage(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self._workers: list[QThread] = []
        self._image_worker: ImageWorker | None = None
        self._presentation_worker: PresentationWorker | None = None
        self._video_worker: VideoWorker | None = None
        self._gh_worker: GitHubWorker | None = None
        self._gh_install_worker: GhInstallWorker | None = None
        self._last_image = ""
        self._last_deck = ""
        self._last_video = ""
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(34, 26, 34, 24)
        root.setSpacing(13)
        header = QVBoxLayout()
        title = QLabel("Медиа-студия")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Настоящие изображения, PPTX-презентации и MP4-видео. Плюс публичный GitHub "
            "и официальный CLI для приватных репозиториев."
        )
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        header.addWidget(title)
        header.addWidget(subtitle)
        root.addLayout(header)

        banner = QFrame()
        banner.setObjectName("Banner")
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(14, 10, 14, 10)
        note = QLabel(
            "Изображения: Pollinations без ключа, бесплатный лимит ≈1 кадр / 45 секунд. "
            "Видео: если сеть недоступна, кадры рисуются локально, но MP4 всё равно реальный. "
            "GitHub: публичное — без ключа; приватное — только через официальный gh auth login."
        )
        note.setWordWrap(True)
        note.setObjectName("Muted")
        banner_layout.addWidget(note)
        root.addWidget(banner)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_image_tab(), "Изображение")
        self.tabs.addTab(self._build_presentation_tab(), "Презентация")
        self.tabs.addTab(self._build_video_tab(), "Видео")
        self.tabs.addTab(self._build_github_tab(), "GitHub")
        root.addWidget(self.tabs, 1)

    # ------------------------------------------------------------------ image
    def _build_image_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(14)

        controls = QFrame()
        controls.setObjectName("Card")
        form = QVBoxLayout(controls)
        form.setContentsMargins(16, 14, 16, 14)
        form.setSpacing(9)
        form.addWidget(QLabel("Что нарисовать"))
        self.image_prompt = QPlainTextEdit()
        self.image_prompt.setPlaceholderText(
            "Например: кинематографичный неоновый город под дождём, отражения, "
            "тёплый свет, без текста и водяных знаков"
        )
        self.image_prompt.setMinimumHeight(130)
        form.addWidget(self.image_prompt)
        row = QHBoxLayout()
        self.image_aspect = QComboBox()
        for label, width, height in (
            ("1:1", 1024, 1024), ("16:9", 1280, 720),
            ("9:16", 720, 1280), ("4:3", 1024, 768),
        ):
            self.image_aspect.addItem(label, (width, height))
        self.image_model = QComboBox()
        self.image_model.addItem("auto", "auto")
        self.image_model.addItem("turbo", "turbo")
        self.image_model.addItem("flux", "flux")
        row.addWidget(QLabel("Формат"))
        row.addWidget(self.image_aspect)
        row.addWidget(QLabel("Модель"))
        row.addWidget(self.image_model)
        row.addStretch(1)
        form.addLayout(row)
        self.image_btn = QPushButton("✦  Сгенерировать изображение")
        self.image_btn.setObjectName("Accent")
        self.image_btn.clicked.connect(self.generate_image)
        form.addWidget(self.image_btn)
        self.image_progress = QProgressBar()
        self.image_progress.setRange(0, 0)
        self.image_progress.setVisible(False)
        form.addWidget(self.image_progress)
        self.image_status = QLabel(
            "Лимит бесплатного сервиса может добавить паузу до 48 секунд."
        )
        self.image_status.setObjectName("Tiny")
        self.image_status.setWordWrap(True)
        form.addWidget(self.image_status)
        form.addStretch(1)
        open_folder = QPushButton("Открыть папку изображений")
        open_folder.setObjectName("Ghost")
        open_folder.clicked.connect(lambda: self._open_dir(output_dir("images")))
        form.addWidget(open_folder)
        controls.setMaximumWidth(430)
        layout.addWidget(controls)

        preview_card, preview_layout = _card("Предпросмотр")
        self.image_preview = QLabel("Здесь появится готовое изображение")
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setObjectName("Muted")
        self.image_preview.setMinimumSize(420, 360)
        self.image_preview.setStyleSheet(
            "QLabel { background:#0e0f14; border:1px solid #252731; border-radius:14px; }"
        )
        preview_layout.addWidget(self.image_preview, 1)
        self.image_meta = QLabel("")
        self.image_meta.setObjectName("Tiny")
        self.image_meta.setWordWrap(True)
        preview_layout.addWidget(self.image_meta)
        row = QHBoxLayout()
        self.open_image_btn = QPushButton("Открыть файл")
        self.open_image_btn.setObjectName("Ghost")
        self.open_image_btn.setEnabled(False)
        self.open_image_btn.clicked.connect(lambda: self._open_file(self._last_image))
        row.addWidget(self.open_image_btn)
        row.addStretch(1)
        preview_layout.addLayout(row)
        layout.addWidget(preview_card, 1)
        return page

    def generate_image(self):
        if self._image_worker and self._image_worker.isRunning():
            return
        prompt = self.image_prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.information(self, "Изображение", "Опишите изображение.")
            return
        width, height = self.image_aspect.currentData()
        worker = ImageWorker(prompt, width, height, str(self.image_model.currentData()), self)
        self._image_worker = worker
        self.image_btn.setEnabled(False)
        self.image_progress.setVisible(True)
        self.image_status.setText("Генерирую…")
        worker.progress.connect(self.image_status.setText)
        worker.done.connect(self._image_done)
        worker.error.connect(self._image_error)
        worker.start()

    def _image_done(self, result: dict):
        self.image_btn.setEnabled(True)
        self.image_progress.setVisible(False)
        self._last_image = str(result.get("path") or "")
        self.image_status.setText("Готово: " + Path(self._last_image).name)
        self.image_meta.setText(
            f"{result.get('width')}×{result.get('height')} · {result.get('model')} · "
            f"{result.get('bytes', 0) / 1024:.0f} КБ\n{self._last_image}"
        )
        pix = QPixmap(self._last_image)
        if not pix.isNull():
            self.image_preview.setPixmap(pix.scaled(
                760, 540, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        self.open_image_btn.setEnabled(bool(self._last_image))
        self.ctx.events.toast.emit("Изображение готово.")

    def _image_error(self, message: str):
        self.image_btn.setEnabled(True)
        self.image_progress.setVisible(False)
        self.image_status.setText("Ошибка: " + message)
        QMessageBox.warning(self, "Изображение", message)

    # ----------------------------------------------------------- presentation
    def _build_presentation_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(10)
        card, form = _card(
            "PPTX-презентация", "Реальный .pptx через python-pptx. Иллюстрации — Pollinations, "
            "план — локальный ИИ или структурный fallback.",
        )
        self.deck_topic = QLineEdit()
        self.deck_topic.setPlaceholderText("Тема: например, «Локальный ИИ в образовании»")
        form.addWidget(self.deck_topic)
        row = QHBoxLayout()
        self.deck_audience = QLineEdit()
        self.deck_audience.setPlaceholderText("Аудитория (необязательно)")
        row.addWidget(self.deck_audience, 1)
        row.addWidget(QLabel("Слайдов"))
        self.deck_slides = QSpinBox()
        self.deck_slides.setRange(4, 12)
        self.deck_slides.setValue(6)
        row.addWidget(self.deck_slides)
        form.addLayout(row)
        self.deck_ai = QCheckBox("Использовать локальный ИИ для структуры")
        self.deck_ai.setChecked(True)
        self.deck_images = QCheckBox("Добавить иллюстрации Pollinations (может занять 2–3 минуты)")
        form.addWidget(self.deck_ai)
        form.addWidget(self.deck_images)
        self.deck_btn = QPushButton("Собрать настоящий PPTX")
        self.deck_btn.setObjectName("Accent")
        self.deck_btn.clicked.connect(self.generate_presentation)
        form.addWidget(self.deck_btn)
        self.deck_progress = QProgressBar()
        self.deck_progress.setRange(0, 0)
        self.deck_progress.setVisible(False)
        form.addWidget(self.deck_progress)
        self.deck_status = QLabel("Файл сохраняется в папку AURA Studio/generated/presentations.")
        self.deck_status.setObjectName("Tiny")
        self.deck_status.setWordWrap(True)
        form.addWidget(self.deck_status)
        row = QHBoxLayout()
        self.open_deck_btn = QPushButton("Открыть PPTX")
        self.open_deck_btn.setEnabled(False)
        self.open_deck_btn.clicked.connect(lambda: self._open_file(self._last_deck))
        folder = QPushButton("Папка презентаций")
        folder.setObjectName("Ghost")
        folder.clicked.connect(lambda: self._open_dir(output_dir("presentations")))
        row.addWidget(self.open_deck_btn)
        row.addWidget(folder)
        row.addStretch(1)
        form.addLayout(row)
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def generate_presentation(self):
        if self._presentation_worker and self._presentation_worker.isRunning():
            return
        topic = self.deck_topic.text().strip()
        if not topic:
            QMessageBox.information(self, "Презентация", "Укажите тему.")
            return
        worker = PresentationWorker(
            self.ctx, topic, self.deck_audience.text().strip(),
            int(self.deck_slides.value()), self.deck_ai.isChecked(),
            self.deck_images.isChecked(), self,
        )
        self._presentation_worker = worker
        self.deck_btn.setEnabled(False)
        self.deck_progress.setVisible(True)
        self.deck_status.setText("Собираю презентацию…")
        worker.progress.connect(self.deck_status.setText)
        worker.done.connect(self._deck_done)
        worker.error.connect(self._deck_error)
        worker.start()

    def _deck_done(self, result: dict):
        self.deck_btn.setEnabled(True)
        self.deck_progress.setVisible(False)
        self._last_deck = str(result.get("path") or "")
        outline = result.get("outline") or {}
        self.deck_status.setText(
            f"Готово: {Path(self._last_deck).name} · слайдов: {result.get('slides')} · "
            f"иллюстраций: {len(result.get('images') or [])} · план: {result.get('generated_by')}\n"
            f"{self._last_deck}"
        )
        self.open_deck_btn.setEnabled(bool(self._last_deck))
        self.ctx.events.toast.emit(
            f"Презентация «{outline.get('title') or ''}» готова."
        )

    def _deck_error(self, message: str):
        self.deck_btn.setEnabled(True)
        self.deck_progress.setVisible(False)
        self.deck_status.setText("Ошибка: " + message)
        QMessageBox.warning(self, "Презентация", message)

    # ------------------------------------------------------------------ video
    def _build_video_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(14)
        controls = QFrame()
        controls.setObjectName("Card")
        form = QVBoxLayout(controls)
        form.setContentsMargins(16, 14, 16, 14)
        form.setSpacing(9)
        form.addWidget(QLabel("Сюжет видео"))
        self.video_prompt = QPlainTextEdit()
        self.video_prompt.setPlaceholderText(
            "Например: абстрактное путешествие через неоновые волны, "
            "плавные переходы, кинематографичный свет"
        )
        self.video_prompt.setMinimumHeight(90)
        form.addWidget(self.video_prompt)
        row = QHBoxLayout()
        row.addWidget(QLabel("Кадров"))
        self.video_frames = QSpinBox()
        self.video_frames.setRange(2, 8)
        self.video_frames.setValue(3)
        row.addWidget(self.video_frames)
        row.addWidget(QLabel("Секунд на кадр"))
        self.video_seconds = QDoubleSpinBox()
        self.video_seconds.setRange(1.5, 10.0)
        self.video_seconds.setValue(3.0)
        row.addWidget(self.video_seconds)
        form.addLayout(row)
        row = QHBoxLayout()
        self.video_size = QComboBox()
        for label, width, height in (
            ("16:9 · 1280×720", 1280, 720), ("16:9 · 960×540", 960, 540),
            ("9:16 · 720×1280", 720, 1280), ("1:1 · 720×720", 720, 720),
        ):
            self.video_size.addItem(label, (width, height))
        row.addWidget(self.video_size, 1)
        form.addLayout(row)
        self.video_ai = QCheckBox("Использовать AI-кадры Pollinations (медленно, лимит 45 с/кадр)")
        self.video_ai.setChecked(True)
        self.video_music = QCheckBox("Добавить оригинальную музыку AURA")
        self.video_music.setChecked(True)
        form.addWidget(self.video_ai)
        form.addWidget(self.video_music)
        form.addWidget(QLabel("Закадровый текст (озвучит Windows SAPI)"))
        self.video_narration = QPlainTextEdit()
        self.video_narration.setMaximumHeight(85)
        self.video_narration.setPlaceholderText("Необязательно. Если пусто — будет только музыка.")
        form.addWidget(self.video_narration)
        self.video_btn = QPushButton("▶  Собрать MP4")
        self.video_btn.setObjectName("Accent")
        self.video_btn.clicked.connect(self.generate_video)
        form.addWidget(self.video_btn)
        self.video_progress = QProgressBar()
        self.video_progress.setRange(0, 0)
        self.video_progress.setVisible(False)
        form.addWidget(self.video_progress)
        form.addStretch(1)
        controls.setMaximumWidth(450)
        layout.addWidget(controls)

        preview, preview_layout = _card("Результат")
        self.video_status = QLabel(
            "Видео кодируется реальным ffmpeg. При отключённых AI-кадрах используется "
            "локальная градиентная анимация — это не заглушка, а готовый MP4."
        )
        self.video_status.setObjectName("Muted")
        self.video_status.setWordWrap(True)
        preview_layout.addWidget(self.video_status)
        self.video_meta = QLabel("")
        self.video_meta.setObjectName("Tiny")
        self.video_meta.setWordWrap(True)
        preview_layout.addWidget(self.video_meta)
        self.open_video_btn = QPushButton("Открыть MP4")
        self.open_video_btn.setEnabled(False)
        self.open_video_btn.clicked.connect(lambda: self._open_file(self._last_video))
        preview_layout.addWidget(self.open_video_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        folder = QPushButton("Папка видео")
        folder.setObjectName("Ghost")
        folder.clicked.connect(lambda: self._open_dir(output_dir("videos")))
        preview_layout.addWidget(folder, alignment=Qt.AlignmentFlag.AlignLeft)
        preview_layout.addStretch(1)
        layout.addWidget(preview, 1)
        return page

    def generate_video(self):
        if self._video_worker and self._video_worker.isRunning():
            return
        prompt = self.video_prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.information(self, "Видео", "Опишите сюжет видео.")
            return
        width, height = self.video_size.currentData()
        narration = self.video_narration.toPlainText().strip()
        worker = VideoWorker(
            self.ctx, prompt, int(self.video_frames.value()), float(self.video_seconds.value()),
            width, height, self.video_ai.isChecked(), narration, self.video_music.isChecked(),
        )
        self._video_worker = worker
        self.video_btn.setEnabled(False)
        self.video_progress.setVisible(True)
        self.video_status.setText("Собираю видео…")
        worker.progress.connect(self.video_status.setText)
        worker.done.connect(self._video_done)
        worker.error.connect(self._video_error)
        worker.start()

    def _video_done(self, result: dict):
        self.video_btn.setEnabled(True)
        self.video_progress.setVisible(False)
        self._last_video = str(result.get("path") or "")
        self.video_status.setText("Готово.")
        self.video_meta.setText(
            f"{result.get('duration', 0):.1f} с · {result.get('bytes', 0) / (1024 * 1024):.2f} МБ · "
            f"рендер {result.get('elapsed', 0):.1f} с\n{self._last_video}"
        )
        self.open_video_btn.setEnabled(bool(self._last_video))
        self.ctx.events.toast.emit("MP4 готов.")

    def _video_error(self, message: str):
        self.video_btn.setEnabled(True)
        self.video_progress.setVisible(False)
        self.video_status.setText("Ошибка: " + message)
        QMessageBox.warning(self, "Видео", message)

    # ----------------------------------------------------------------- GitHub
    def _build_github_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(14)
        left = QVBoxLayout()
        card, form = _card(
            "Публичный GitHub без ключа",
            "Профиль и репозитории читаются из официального публичного API. "
            "Лимит без входа — 60 запросов в час.",
        )
        self.github_user = QLineEdit()
        self.github_user.setPlaceholderText("GitHub-логин, например octocat")
        form.addWidget(self.github_user)
        row = QHBoxLayout()
        profile = QPushButton("Профиль и репозитории")
        profile.setObjectName("Accent")
        profile.clicked.connect(lambda: self.github_profile())
        row.addWidget(profile)
        open_site = QPushButton("Открыть github.com")
        open_site.setObjectName("Ghost")
        open_site.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com")))
        row.addWidget(open_site)
        form.addLayout(row)
        form.addWidget(QLabel("Поиск репозиториев"))
        self.github_search = QLineEdit()
        self.github_search.setPlaceholderText("Например: local ai music player")
        form.addWidget(self.github_search)
        search = QPushButton("Найти репозитории")
        search.clicked.connect(self.github_search_repos)
        form.addWidget(search)
        left.addWidget(card)

        cli, cli_form = _card(
            "GitHub CLI · приватные репозитории и push",
            "AURA не просит и не хранит ваш GitHub-токен. Вход выполняет официальный gh; "
            "учётные данные остаются в его конфигурации.",
        )
        self.gh_status = QLabel("Статус не проверен")
        self.gh_status.setObjectName("Tiny")
        self.gh_status.setWordWrap(True)
        cli_form.addWidget(self.gh_status)
        row = QHBoxLayout()
        check = QPushButton("Проверить статус")
        check.setObjectName("Ghost")
        check.clicked.connect(self.github_status)
        install = QPushButton("Скачать portable gh")
        install.clicked.connect(self.github_install_cli)
        login = QPushButton("Войти через GitHub CLI")
        login.setObjectName("Accent")
        login.clicked.connect(self.github_login)
        row.addWidget(check)
        row.addWidget(install)
        row.addWidget(login)
        row.addStretch(1)
        cli_form.addLayout(row)
        self.gh_progress = QProgressBar()
        self.gh_progress.setRange(0, 0)
        self.gh_progress.setVisible(False)
        cli_form.addWidget(self.gh_progress)
        left.addWidget(cli)
        left.addStretch(1)
        layout.addLayout(left, 1)

        output_card, output_layout = _card("Результат GitHub")
        self.github_output = QTextBrowser()
        self.github_output.setObjectName("ChatView")
        self.github_output.setPlainText(
            "Введите логин и нажмите «Профиль и репозитории». "
            "Приватные операции требуют официального GitHub CLI."
        )
        output_layout.addWidget(self.github_output, 1)
        layout.addWidget(output_card, 1)
        return page

    def _start_gh(self, action: str, value: str = ""):
        if self._gh_worker and self._gh_worker.isRunning():
            return
        worker = GitHubWorker(self.ctx.settings, action, value, self)
        self._gh_worker = worker
        self.github_output.setPlainText("Запрос к GitHub…")
        worker.done.connect(lambda text: self.github_output.setPlainText(text))
        worker.error.connect(lambda message: self.github_output.setPlainText("Ошибка GitHub:\n" + message))
        worker.start()

    def github_profile(self):
        username = self.github_user.text().strip()
        if not username:
            QMessageBox.information(self, "GitHub", "Введите логин.")
            return
        self.ctx.settings.set("github.username", username)
        self.ctx.settings.save()
        self._start_gh("profile", username)

    def github_search_repos(self):
        query = self.github_search.text().strip()
        if not query:
            QMessageBox.information(self, "GitHub", "Введите поисковый запрос.")
            return
        self._start_gh("search", query)

    def github_status(self):
        self._start_gh("status")

    def github_install_cli(self):
        if self._gh_install_worker and self._gh_install_worker.isRunning():
            return
        if QMessageBox.question(
            self, "GitHub CLI",
            "Скачать официальный portable GitHub CLI с github.com и распаковать в папку "
            "данных AURA? Пользовательские настройки gh останутся отдельными.",
        ) != QMessageBox.StandardButton.Yes:
            return
        worker = GhInstallWorker(self.ctx.settings, self)
        self._gh_install_worker = worker
        self.gh_progress.setVisible(True)
        self.gh_status.setText("Скачиваю GitHub CLI…")
        worker.progress.connect(
            lambda done, total, text: self.gh_status.setText(
                f"{text} · {done / 1048576:.1f} МБ" + (f" / {total / 1048576:.1f} МБ" if total else "")
            )
        )
        worker.done.connect(self._gh_installed)
        worker.error.connect(self._gh_install_error)
        worker.start()

    def _gh_installed(self, path: str):
        self.gh_progress.setVisible(False)
        self.gh_status.setText("GitHub CLI установлен: " + path)
        self.ctx.events.toast.emit("GitHub CLI установлен. Теперь можно выполнить вход.")
        self.github_status()

    def _gh_install_error(self, message: str):
        self.gh_progress.setVisible(False)
        self.gh_status.setText("Ошибка установки: " + message)
        QMessageBox.warning(self, "GitHub CLI", message)

    def github_login(self):
        try:
            github.open_gh_login(self.ctx.settings)
            self.ctx.events.toast.emit(
                "Открыто окно gh auth login. Завершите вход в браузере и нажмите «Проверить статус»."
            )
        except Exception as exc:
            QMessageBox.warning(self, "GitHub CLI", str(exc))

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _open_file(path: str):
        if path and Path(path).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    @staticmethod
    def _open_dir(path: Path):
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    # --------------------------------------------------------------- lifecycle
    def shutdown(self):
        for worker in (
            self._image_worker, self._presentation_worker, self._video_worker,
            self._gh_worker, self._gh_install_worker,
        ):
            if worker and worker.isRunning():
                if isinstance(worker, GhInstallWorker):
                    worker.cancelled = True
                worker.wait(2500)
