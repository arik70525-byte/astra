"""Public OSINT page with explicit legal limits."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote_plus

from PySide6.QtCore import QThread, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTextBrowser, QVBoxLayout, QWidget,
)

from core import osint
from ui.context import AppContext


class OsintWorker(QThread):
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, kind: str, target: str, settings, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.target = target
        self.settings = settings

    def run(self):
        try:
            if self.kind == "domain":
                data = osint.domain_report(self.target)
            elif self.kind == "ip":
                data = osint.ip_report(self.target)
            elif self.kind == "username":
                data = osint.username_report(self.target)
            elif self.kind == "email":
                data = osint.email_report(self.target)
            elif self.kind == "company":
                data = osint.company_report(self.target)
            elif self.kind == "github":
                data = osint.github_report(self.target)
            else:
                raise ValueError("Неизвестный тип проверки.")
            self.done.emit(data)
        except Exception as exc:
            self.error.emit(str(exc))


class OsintPage(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self._worker: OsintWorker | None = None
        self._last_data: dict | None = None
        self._last_report = ""
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 28, 34, 28)
        layout.setSpacing(13)
        header = QHBoxLayout()
        title = QLabel("Публичные исследования")
        title.setObjectName("PageTitle")
        header.addWidget(title)
        header.addStretch(1)
        copy_btn = QPushButton("Копировать отчёт")
        copy_btn.setObjectName("Ghost")
        copy_btn.clicked.connect(self._copy)
        save_btn = QPushButton("Сохранить .txt")
        save_btn.setObjectName("Ghost")
        save_btn.clicked.connect(self._save)
        header.addWidget(copy_btn)
        header.addWidget(save_btn)
        layout.addLayout(header)

        banner = QFrame()
        banner.setObjectName("Banner")
        b_layout = QHBoxLayout(banner)
        b_layout.setContentsMargins(14, 11, 14, 11)
        text = QLabel(
            "Только открытые данные: DNS/RDAP/TLS, IP-геолокация, публичные профили по нику, "
            "Gravatar по вашему e-mail, реестры компаний GLEIF/SEC и публичный GitHub. "
            "Нет поиска телефона, ФИО, адреса, паспорта, СНИЛС, частных аккаунтов, утечек, "
            "платных/закрытых баз и деанонимизации. Не используйте для преследования."
        )
        text.setWordWrap(True)
        text.setObjectName("Muted")
        b_layout.addWidget(text)
        layout.addWidget(banner)

        form = QFrame()
        form.setObjectName("Card")
        f_layout = QHBoxLayout(form)
        f_layout.setContentsMargins(14, 14, 14, 14)
        f_layout.setSpacing(10)
        self.kind = QComboBox()
        self.kind.addItem("Домен · DNS/RDAP/TLS", "domain")
        self.kind.addItem("IP-адрес · ASN/гео", "ip")
        self.kind.addItem("Публичный ник · 16 платформ", "username")
        self.kind.addItem("Мой e-mail · Gravatar", "email")
        self.kind.addItem("Компания · GLEIF/SEC", "company")
        self.kind.addItem("GitHub · профиль и репозитории", "github")
        self.kind.currentIndexChanged.connect(self._kind_changed)
        f_layout.addWidget(self.kind)
        self.target = QLineEdit()
        self.target.setPlaceholderText("example.com")
        self.target.returnPressed.connect(self.run)
        f_layout.addWidget(self.target, 1)
        self.consent = QCheckBox("Это мой e-mail")
        self.consent.setVisible(False)
        self.consent.setToolTip("Gravatar проверяет только публичный профиль, связанный с адресом.")
        f_layout.addWidget(self.consent)
        self.run_btn = QPushButton("Проверить")
        self.run_btn.setObjectName("Accent")
        self.run_btn.clicked.connect(self.run)
        f_layout.addWidget(self.run_btn)
        layout.addWidget(form)

        self.status = QLabel(osint.DISCLAIMER)
        self.status.setObjectName("Tiny")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.result = QTextBrowser()
        self.result.setObjectName("ChatView")
        self.result.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        self.result.setPlainText(
            "Введите цель и нажмите «Проверить».\n\n"
            "Примеры:\n"
            "  example.com — DNS, SPF/DMARC, RDAP, TLS, security.txt, crt.sh\n"
            "  1.1.1.1 — ASN, геолокация, Shodan InternetDB\n"
            "  octocat — публичные профили на 16 платформах\n"
            "  octocat — GitHub: профиль и последние репозитории\n"
            "  Microsoft — GLEIF и SEC EDGAR\n"
            "  you@example.com — только публичный Gravatar, с подтверждением\n\n"
            "Все запросы идут напрямую с вашего компьютера в публичные API."
        )
        layout.addWidget(self.result, 1)

        bottom = QHBoxLayout()
        for label, url in (
            ("Яндекс", "https://yandex.ru/search/?text="),
            ("Google", "https://www.google.com/search?q="),
            ("DuckDuckGo", "https://duckduckgo.com/?q="),
        ):
            button = QPushButton(label)
            button.setObjectName("Ghost")
            button.clicked.connect(lambda _=False, u=url: self._open_search(u))
            bottom.addWidget(button)
        ask = QPushButton("✦  Сравнить с ИИ")
        ask.setObjectName("Ghost")
        ask.setToolTip("Вставить отчёт в AI-чат. Отправку подтверждаете вы.")
        ask.clicked.connect(self._ask_ai)
        bottom.addWidget(ask)
        bottom.addStretch(1)
        note = QLabel("Ссылки открывают поиск в браузере; AURA не собирает выдачу Google/Яндекса.")
        note.setObjectName("Tiny")
        bottom.addWidget(note)
        layout.addLayout(bottom)

    def _open_search(self, base: str):
        query = self.target.text().strip() or "AURA Studio"
        target = base + quote_plus(query)
        if self.kind.currentData() == "username":
            target = base + quote_plus(f'"{query}" профиль')
        QDesktopServices.openUrl(QUrl(target))
        self.status.setText("Поиск открыт в браузере. Проверяйте источники вручную.")

    def _ask_ai(self):
        if not self._last_report:
            QMessageBox.information(
                self, "AI-сравнение",
                "Сначала получите отчёт по домену, IP, нику или компании.",
            )
            return
        prompt = (
            "Ниже отчёт AURA OSINT из открытых публичных источников. "
            "Сравни источники, отметь совпадающие факты, противоречия и пробелы. "
            "Не делай выводов о частном лице и не пытайся деанонимизировать. "
            "Каждый важный вывод сопровождай ссылкой или названием источника.\n\n"
            + self._last_report[-12000:]
        )
        self.ctx.events.ask_ai.emit(prompt)

    def _kind_changed(self):
        kind = self.kind.currentData()
        self.consent.setVisible(kind == "email")
        placeholders = {
            "domain": "example.com",
            "ip": "1.1.1.1",
            "username": "octocat",
            "email": "you@example.com",
            "company": "Microsoft",
            "github": "octocat",
        }
        self.target.setPlaceholderText(placeholders.get(kind, ""))

    def run(self):
        if self._worker and self._worker.isRunning():
            return
        target = self.target.text().strip()
        if not target:
            self.status.setText("Введите цель проверки.")
            return
        kind = str(self.kind.currentData())
        if kind == "email" and not self.consent.isChecked():
            QMessageBox.information(
                self, "Проверка e-mail",
                "Подтвердите, что это ваш e-mail. Проверяется только публичный профиль "
                "Gravatar; AURA не ищет утечки, пароли или частные аккаунты.",
            )
            return
        self.run_btn.setEnabled(False)
        self.status.setText(f"Проверяю {target}…")
        self.result.setPlainText("Запрос выполняется…")
        self._worker = OsintWorker(kind, target, self.ctx.settings, self)
        self._worker.done.connect(self._done)
        self._worker.error.connect(self._error)
        self._worker.start()

    def _done(self, data: dict):
        self._last_data = data
        self._last_report = osint.format_report(data)
        self.result.setPlainText(self._last_report)
        self.status.setText("Готово. Данные получены из публичных источников.")
        self.run_btn.setEnabled(True)

    def _error(self, message: str):
        self.status.setText("Ошибка: " + message)
        self.result.setPlainText("Ошибка:\n" + message)
        self.run_btn.setEnabled(True)

    def _copy(self):
        if self._last_report:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(self._last_report)
            self.status.setText("Отчёт скопирован в буфер обмена.")

    def _save(self):
        if not self._last_report:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить отчёт", "aura_osint_report.txt", "Текст (*.txt)"
        )
        if path:
            Path(path).write_text(self._last_report, encoding="utf-8")
            self.status.setText(f"Сохранено: {path}")
