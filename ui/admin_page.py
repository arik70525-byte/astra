"""Administrator page: local users, roles and account state."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from core.auth import AuthError, AuthManager
from core.i18n import tr


class CreateUserDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Новый пользователь")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        title = QLabel("Создать локального пользователя")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        form = QFormLayout()
        form.setSpacing(8)
        self.username = QLineEdit()
        self.username.setPlaceholderText("3–32 символа")
        self.display_name = QLineEdit()
        self.display_name.setPlaceholderText("Как показывать в интерфейсе")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Минимум 8 символов")
        self.password2 = QLineEdit()
        self.password2.setEchoMode(QLineEdit.EchoMode.Password)
        self.role = QComboBox()
        self.role.addItem(tr(settings, "admin.role_user"), "user")
        self.role.addItem(tr(settings, "admin.role_admin"), "admin")
        form.addRow(tr(settings, "auth.username"), self.username)
        form.addRow(tr(settings, "auth.display_name"), self.display_name)
        form.addRow(tr(settings, "auth.password"), self.password)
        form.addRow(tr(settings, "auth.password_again"), self.password2)
        form.addRow("Роль", self.role)
        layout.addLayout(form)
        self.status = QLabel("")
        self.status.setStyleSheet("color:#ff8d9b;")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton(tr(settings, "common.cancel"))
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(self.reject)
        create = QPushButton("Создать")
        create.setObjectName("Accent")
        create.clicked.connect(self._create)
        row.addWidget(cancel)
        row.addWidget(create)
        layout.addLayout(row)

    def _create(self):
        if self.password.text() != self.password2.text():
            self.status.setText("Пароли не совпадают.")
            return
        self._values = {
            "username": self.username.text().strip(),
            "display_name": self.display_name.text().strip(),
            "password": self.password.text(),
            "role": str(self.role.currentData()),
        }
        self.accept()


class PasswordDialog(QDialog):
    def __init__(self, username: str, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Сброс пароля")
        self.setMinimumWidth(390)
        layout = QVBoxLayout(self)
        title = QLabel(f"Новый пароль для «{username}»")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Минимум 8 символов")
        self.password2 = QLineEdit()
        self.password2.setEchoMode(QLineEdit.EchoMode.Password)
        self.password2.setPlaceholderText("Повторите пароль")
        layout.addWidget(self.password)
        layout.addWidget(self.password2)
        self.status = QLabel("")
        self.status.setStyleSheet("color:#ff8d9b;")
        layout.addWidget(self.status)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton(tr(settings, "common.cancel"))
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(self.reject)
        save = QPushButton(tr(settings, "common.save"))
        save.setObjectName("Accent")
        save.clicked.connect(self._save)
        row.addWidget(cancel)
        row.addWidget(save)
        layout.addLayout(row)

    def _save(self):
        if self.password.text() != self.password2.text():
            self.status.setText("Пароли не совпадают.")
            return
        self._password = self.password.text()
        self.accept()


class AdminPage(QWidget):
    def __init__(self, auth: AuthManager, current_user: dict[str, Any], settings, parent=None):
        super().__init__(parent)
        self.auth = auth
        self.current_user = current_user
        self.settings = settings
        self._build()
        self.refresh()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 28, 34, 26)
        layout.setSpacing(12)
        header = QHBoxLayout()
        title = QLabel(tr(self.settings, "admin.title"))
        title.setObjectName("PageTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.refresh_btn = QPushButton(tr(self.settings, "admin.refresh"))
        self.refresh_btn.setObjectName("Ghost")
        self.refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self.refresh_btn)
        layout.addLayout(header)
        subtitle = QLabel(tr(self.settings, "admin.subtitle"))
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        stats = QHBoxLayout()
        self.card_users = self._stat("0", tr(self.settings, "admin.users"))
        self.card_active = self._stat("0", tr(self.settings, "admin.active"))
        self.card_admins = self._stat("0", tr(self.settings, "admin.admins"))
        self.card_last = self._stat("—", tr(self.settings, "admin.last_login"))
        for card in (self.card_users, self.card_active, self.card_admins, self.card_last):
            stats.addWidget(card)
        stats.addStretch(1)
        layout.addLayout(stats)

        actions = QHBoxLayout()
        create = QPushButton("+  " + tr(self.settings, "admin.create"))
        create.setObjectName("Accent")
        create.clicked.connect(self.create_user)
        reset = QPushButton(tr(self.settings, "admin.reset"))
        reset.setObjectName("Ghost")
        reset.clicked.connect(self.reset_password)
        toggle = QPushButton(tr(self.settings, "admin.toggle"))
        toggle.setObjectName("Ghost")
        toggle.clicked.connect(self.toggle_disabled)
        role = QPushButton(tr(self.settings, "admin.role"))
        role.setObjectName("Ghost")
        role.clicked.connect(self.toggle_role)
        delete = QPushButton(tr(self.settings, "admin.delete"))
        delete.setObjectName("Ghost")
        delete.setStyleSheet("color:#ff8d9b;")
        delete.clicked.connect(self.delete_user)
        for button in (create, reset, toggle, role, delete):
            actions.addWidget(button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Пользователь", "Имя", "Роль", "Статус", "Создан", "Последний вход"
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(False)
        self.table.doubleClicked.connect(lambda _: self.toggle_disabled())
        layout.addWidget(self.table, 1)

        note = QLabel(tr(self.settings, "admin.local_only"))
        note.setObjectName("Tiny")
        note.setWordWrap(True)
        layout.addWidget(note)

    def _stat(self, value: str, caption: str) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        box = QVBoxLayout(card)
        box.setContentsMargins(15, 10, 15, 10)
        box.setSpacing(1)
        number = QLabel(value)
        number.setStyleSheet("font-size:22px; font-weight:750;")
        caption_label = QLabel(caption)
        caption_label.setObjectName("Muted")
        caption_label.setStyleSheet("font-size:10px;")
        box.addWidget(number)
        box.addWidget(caption_label)
        card._number = number
        return card

    def refresh(self):
        summary = self.auth.summary()
        self.card_users._number.setText(str(summary["users"]))
        self.card_active._number.setText(str(summary["active"]))
        self.card_admins._number.setText(str(summary["admins"]))
        last = str(summary.get("last_login") or "")
        self.card_last._number.setText(last.replace("T", " ")[:16] if last else "—")
        users = self.auth.list_users()
        self.table.setRowCount(len(users))
        for row, user in enumerate(users):
            self._set_row(row, user)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    def _set_row(self, row: int, user: dict[str, Any]):
        username = QTableWidgetItem(str(user.get("username") or ""))
        username.setData(Qt.ItemDataRole.UserRole, int(user["id"]))
        if int(user["id"]) == int(self.current_user["id"]):
            username.setText(username.text() + "  (вы)")
        self.table.setItem(row, 0, username)
        self.table.setItem(row, 1, QTableWidgetItem(str(user.get("display_name") or "")))
        role = tr(self.settings, "admin.role_admin") if user.get("role") == "admin" else tr(self.settings, "admin.role_user")
        self.table.setItem(row, 2, QTableWidgetItem(role))
        status = tr(self.settings, "admin.disabled") if user.get("disabled") else tr(self.settings, "admin.enabled")
        self.table.setItem(row, 3, QTableWidgetItem(status))
        self.table.setItem(row, 4, QTableWidgetItem(str(user.get("created_at") or "").replace("T", " ")[:16]))
        self.table.setItem(row, 5, QTableWidgetItem(str(user.get("last_login") or "—").replace("T", " ")[:16]))

    def _selected(self) -> dict[str, Any] | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        user_id = item.data(Qt.ItemDataRole.UserRole)
        return self.auth.get_user(int(user_id)) if user_id is not None else None

    def create_user(self):
        dialog = CreateUserDialog(self.settings, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = getattr(dialog, "_values", {})
        try:
            self.auth.create_user(
                values.get("username", ""), values.get("password", ""),
                values.get("display_name", ""), values.get("role", "user"),
                actor=str(self.current_user.get("username") or ""),
            )
        except AuthError as exc:
            QMessageBox.warning(self, "Пользователь", str(exc))
            return
        self.refresh()

    def reset_password(self):
        user = self._selected()
        if not user:
            QMessageBox.information(self, "Пользователь", "Выберите пользователя в таблице.")
            return
        dialog = PasswordDialog(str(user["username"]), self.settings, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.auth.reset_password(
                int(user["id"]), getattr(dialog, "_password", ""),
                actor_id=int(self.current_user["id"]),
            )
        except AuthError as exc:
            QMessageBox.warning(self, "Пароль", str(exc))
            return
        QMessageBox.information(self, "Пароль", "Пароль изменён. Сообщите его пользователю лично.")

    def toggle_disabled(self):
        user = self._selected()
        if not user:
            QMessageBox.information(self, "Пользователь", "Выберите пользователя в таблице.")
            return
        try:
            self.auth.set_disabled(
                int(user["id"]), not bool(user.get("disabled")),
                actor_id=int(self.current_user["id"]),
            )
        except AuthError as exc:
            QMessageBox.warning(self, "Пользователь", str(exc))
            return
        self.refresh()

    def toggle_role(self):
        user = self._selected()
        if not user:
            QMessageBox.information(self, "Пользователь", "Выберите пользователя в таблице.")
            return
        role = "user" if user.get("role") == "admin" else "admin"
        answer = QMessageBox.question(
            self, "Роль",
            f"Изменить роль «{user['username']}» на «{role}»?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.auth.set_role(int(user["id"]), role, actor_id=int(self.current_user["id"]))
        except AuthError as exc:
            QMessageBox.warning(self, "Роль", str(exc))
            return
        self.refresh()

    def delete_user(self):
        user = self._selected()
        if not user:
            QMessageBox.information(self, "Пользователь", "Выберите пользователя в таблице.")
            return
        answer = QMessageBox.question(
            self, "Удаление",
            f"Удалить учётную запись «{user['username']}»?\nИстория этого пользователя не удаляется автоматически.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.auth.delete_user(int(user["id"]), actor_id=int(self.current_user["id"]))
        except AuthError as exc:
            QMessageBox.warning(self, "Удаление", str(exc))
            return
        self.refresh()

    def showEvent(self, event):  # noqa: N802
        self.refresh()
        super().showEvent(event)
