"""Local sign-in, registration and workspace chooser."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QTabWidget, QVBoxLayout, QWidget,
)

from core.auth import AuthError, AuthManager
from core.i18n import LANGUAGES, tr


def _password_field(placeholder: str) -> QLineEdit:
    field = QLineEdit()
    field.setEchoMode(QLineEdit.EchoMode.Password)
    field.setPlaceholderText(placeholder)
    field.setMinimumHeight(38)
    return field


class AuthDialog(QDialog):
    """Register the first administrator or sign an existing user in."""

    def __init__(self, auth: AuthManager, settings, parent=None):
        super().__init__(parent)
        self.auth = auth
        self.settings = settings
        self.user: dict[str, Any] | None = None
        self.first_run = not auth.has_users()
        self.setWindowTitle("AURA Studio")
        self.setMinimumSize(880, 580)
        self.resize(920, 610)
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        brand = QFrame()
        brand.setObjectName("AuthBrand")
        brand.setFixedWidth(350)
        brand.setStyleSheet(
            "QFrame#AuthBrand { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #22152d, stop:0.55 #15121f, stop:1 #0b0b0e);"
            "border-right: 1px solid #2a2534; }"
        )
        b = QVBoxLayout(brand)
        b.setContentsMargins(32, 38, 30, 30)
        b.setSpacing(10)
        logo_row = QHBoxLayout()
        logo = QLabel("AURA")
        logo.setStyleSheet("font-size:30px; font-weight:800; letter-spacing:1px;")
        dot = QLabel(".")
        dot.setStyleSheet("font-size:34px; font-weight:800; color:#ff5bc8;")
        logo_row.addWidget(logo)
        logo_row.addWidget(dot)
        logo_row.addStretch(1)
        b.addLayout(logo_row)
        tagline = QLabel(tr(self.settings, "app.tagline"))
        tagline.setStyleSheet("font-size:9px; letter-spacing:1.8px; color:#746b83;")
        b.addWidget(tagline)
        b.addSpacing(36)
        hero = QLabel("Локальный ИИ.\nБез облака.")
        hero.setStyleSheet("font-size:27px; font-weight:750; line-height:1.1;")
        b.addWidget(hero)
        subtitle = QLabel(tr(self.settings, "auth.subtitle"))
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color:#a7a1b5; font-size:12px; line-height:1.5;")
        b.addWidget(subtitle)
        b.addSpacing(22)
        for text in (
            "✦  Две локальные модели",
            "⌘  Python-песочница",
            "◎  Законный OSINT",
            "♫  Музыка и плейлисты",
        ):
            label = QLabel(text)
            label.setStyleSheet("color:#d9d2e7; font-size:12px; padding:5px 0;")
            b.addWidget(label)
        b.addStretch(1)
        note = QLabel(tr(self.settings, "auth.local_note"))
        note.setWordWrap(True)
        note.setStyleSheet("color:#6e687a; font-size:10px;")
        b.addWidget(note)
        root.addWidget(brand)

        right = QWidget()
        r = QVBoxLayout(right)
        r.setContentsMargins(34, 30, 34, 26)
        r.setSpacing(12)
        title = QLabel(tr(self.settings, "auth.welcome"))
        title.setObjectName("PageTitle")
        title.setStyleSheet("font-size:28px;")
        r.addWidget(title)
        self.subtitle = QLabel(
            tr(self.settings, "auth.first_run") if self.first_run else tr(self.settings, "auth.subtitle")
        )
        self.subtitle.setObjectName("Muted")
        self.subtitle.setWordWrap(True)
        r.addWidget(self.subtitle)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_login(), tr(self.settings, "auth.sign_in"))
        self.tabs.addTab(self._build_register(), tr(self.settings, "auth.register"))
        if self.first_run:
            self.tabs.setCurrentIndex(1)
            self.tabs.setTabEnabled(0, False)
        else:
            self.tabs.setCurrentIndex(0)
        r.addWidget(self.tabs, 1)

        self.show_passwords = QCheckBox("Показать пароли")
        self.show_passwords.toggled.connect(self._toggle_passwords)
        r.addWidget(self.show_passwords)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#ff8d9b; font-size:11px; min-height:18px;")
        r.addWidget(self.status)
        foot = QHBoxLayout()
        version = QLabel("AURA Studio · local accounts")
        version.setObjectName("Tiny")
        foot.addWidget(version)
        foot.addStretch(1)
        cancel = QPushButton(tr(self.settings, "common.close"))
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(self.reject)
        foot.addWidget(cancel)
        r.addLayout(foot)
        root.addWidget(right, 1)

    def _build_login(self) -> QWidget:
        page = QWidget()
        form = QVBoxLayout(page)
        form.setContentsMargins(2, 12, 2, 2)
        form.setSpacing(7)
        form.addWidget(QLabel(tr(self.settings, "auth.username")))
        self.login_user = QLineEdit()
        self.login_user.setPlaceholderText("username")
        self.login_user.setMinimumHeight(38)
        remembered = str(self.settings.get("auth.last_user", "") or "")
        if remembered and bool(self.settings.get("auth.remember", True)):
            self.login_user.setText(remembered)
        form.addWidget(self.login_user)
        form.addWidget(QLabel(tr(self.settings, "auth.password")))
        self.login_password = _password_field("••••••••")
        form.addWidget(self.login_password)
        self.remember = QCheckBox(tr(self.settings, "auth.remember"))
        self.remember.setChecked(bool(self.settings.get("auth.remember", True)))
        form.addWidget(self.remember)
        form.addSpacing(8)
        self.login_btn = QPushButton(tr(self.settings, "auth.sign_in"))
        self.login_btn.setObjectName("Accent")
        self.login_btn.setMinimumHeight(40)
        self.login_btn.clicked.connect(self._login)
        form.addWidget(self.login_btn)
        self.login_user.returnPressed.connect(self._login)
        self.login_password.returnPressed.connect(self._login)
        form.addStretch(1)
        return page

    def _build_register(self) -> QWidget:
        page = QWidget()
        form = QVBoxLayout(page)
        form.setContentsMargins(2, 12, 2, 2)
        form.setSpacing(7)
        form.addWidget(QLabel(tr(self.settings, "auth.username")))
        self.reg_user = QLineEdit()
        self.reg_user.setPlaceholderText("от 3 до 32 символов")
        self.reg_user.setMinimumHeight(38)
        form.addWidget(self.reg_user)
        form.addWidget(QLabel(tr(self.settings, "auth.display_name")))
        self.reg_name = QLineEdit()
        self.reg_name.setPlaceholderText("Как вас показывать")
        form.addWidget(self.reg_name)
        form.addWidget(QLabel(tr(self.settings, "auth.password")))
        self.reg_password = _password_field("минимум 8 символов")
        form.addWidget(self.reg_password)
        form.addWidget(QLabel(tr(self.settings, "auth.password_again")))
        self.reg_password2 = _password_field("повторите пароль")
        form.addWidget(self.reg_password2)
        form.addSpacing(8)
        self.register_btn = QPushButton(tr(self.settings, "auth.register"))
        self.register_btn.setObjectName("Accent")
        self.register_btn.setMinimumHeight(40)
        self.register_btn.clicked.connect(self._register)
        form.addWidget(self.register_btn)
        self.reg_password2.returnPressed.connect(self._register)
        form.addStretch(1)
        return page

    def _toggle_passwords(self, visible: bool):
        mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        for field in (
            self.login_password, self.reg_password, self.reg_password2,
        ):
            field.setEchoMode(mode)

    def _save_last_user(self, username: str):
        self.settings.set("auth.last_user", username if self.remember.isChecked() else "")
        self.settings.set("auth.remember", bool(self.remember.isChecked()))
        self.settings.save()

    def _login(self):
        if not self.tabs.isTabEnabled(0):
            return
        username = self.login_user.text().strip()
        password = self.login_password.text()
        if not username or not password:
            self.status.setText("Введите имя пользователя и пароль.")
            return
        try:
            self.user = self.auth.authenticate(username, password)
        except AuthError as exc:
            self.status.setText(str(exc))
            self.login_password.selectAll()
            self.login_password.setFocus()
            return
        self._save_last_user(str(self.user["username"]))
        self.accept()

    def _register(self):
        username = self.reg_user.text().strip()
        display = self.reg_name.text().strip()
        password = self.reg_password.text()
        again = self.reg_password2.text()
        if password != again:
            self.status.setText("Пароли не совпадают.")
            return
        try:
            self.user = self.auth.create_user(username, password, display)
        except AuthError as exc:
            self.status.setText(str(exc))
            return
        self.settings.set("auth.last_user", str(self.user["username"]))
        self.settings.save()
        self.accept()


class WorkspaceDialog(QDialog):
    """Post-login workspace chooser."""

    def __init__(self, user: dict[str, Any], settings, parent=None):
        super().__init__(parent)
        self.user = user
        self.settings = settings
        self.workspace = "player"
        self.setWindowTitle("AURA Studio — workspace")
        self.setMinimumSize(820, 530)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 26, 30, 24)
        layout.setSpacing(10)
        title = QLabel(tr(self.settings, "hub.title"))
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        subtitle = QLabel(
            f"{self.user.get('display_name') or self.user.get('username')} · "
            + tr(self.settings, "hub.subtitle")
        )
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        grid = QGridLayout()
        grid.setSpacing(12)
        cards = [
            ("player", "♫", tr(self.settings, "workspace.player"), tr(self.settings, "hub.player_desc")),
            ("sandbox", "⌘", tr(self.settings, "workspace.sandbox"), tr(self.settings, "hub.sandbox_desc")),
            ("osint", "◎", tr(self.settings, "workspace.osint"), tr(self.settings, "hub.osint_desc")),
            ("chat", "✦", tr(self.settings, "workspace.chat"), tr(self.settings, "hub.chat_desc")),
            ("pc", "▣", tr(self.settings, "workspace.pc"), tr(self.settings, "hub.pc_desc")),
        ]
        if str(self.user.get("role")) == "admin":
            cards.append(("admin", "⚙", tr(self.settings, "workspace.admin"), tr(self.settings, "hub.admin_desc")))
        for index, (key, icon, label, description) in enumerate(cards):
            card = QPushButton(f"{icon}   {label}\n{description}")
            card.setObjectName("WorkspaceCard")
            card.setMinimumHeight(104)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            card.setStyleSheet(
                "QPushButton#WorkspaceCard { text-align:left; padding:16px 18px; "
                "border:1px solid #34303f; border-radius:14px; background:#17161e; "
                "font-size:13px; font-weight:600; color:#f4f3f8; }"
                "QPushButton#WorkspaceCard:hover { border-color:#ff5bc8; "
                "background:#211a29; }"
            )
            card.clicked.connect(lambda _=False, k=key: self._choose(k))
            grid.addWidget(card, index // 3, index % 3)
        layout.addLayout(grid, 1)
        foot = QHBoxLayout()
        note = QLabel("Пароль проверен локально. Все разделы остаются в меню.")
        note.setObjectName("Tiny")
        foot.addWidget(note)
        foot.addStretch(1)
        all_btn = QPushButton(tr(self.settings, "workspace.all"))
        all_btn.setObjectName("Ghost")
        all_btn.clicked.connect(lambda: self._choose("all"))
        foot.addWidget(all_btn)
        close = QPushButton(tr(self.settings, "common.close"))
        close.setObjectName("Ghost")
        close.clicked.connect(self.reject)
        foot.addWidget(close)
        layout.addLayout(foot)

    def _choose(self, key: str):
        self.workspace = key
        self.accept()
