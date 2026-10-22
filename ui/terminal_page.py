"""Working PowerShell terminal and Python code sandbox."""
from __future__ import annotations

import ast
import os
import re
import shutil
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, QThread, Qt, Signal
from PySide6.QtGui import (
    QColor, QFont, QKeyEvent, QKeySequence, QShortcut, QSyntaxHighlighter,
    QTextCharFormat, QTextCursor, QTextFormat,
)
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QTabWidget,
    QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
)

from core.sandbox import docker_available, run_python
from ui.context import AppContext


class HistoryLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.history: list[str] = []
        self.position = 0

    def remember(self, command: str):
        if command and (not self.history or self.history[-1] != command):
            self.history.append(command)
        self.position = len(self.history)

    def keyPressEvent(self, event: QKeyEvent):  # noqa: N802
        if event.key() == Qt.Key.Key_Up and self.history:
            self.position = max(0, self.position - 1)
            self.setText(self.history[self.position])
            return
        if event.key() == Qt.Key.Key_Down and self.history:
            self.position = min(len(self.history), self.position + 1)
            self.setText(self.history[self.position] if self.position < len(self.history) else "")
            return
        super().keyPressEvent(event)


class PythonHighlighter(QSyntaxHighlighter):
    """Compact Python syntax highlighter that works without extra packages."""

    def __init__(self, document):
        super().__init__(document)
        self.rules: list[tuple[re.Pattern, QTextCharFormat, int]] = []

        keyword = QTextCharFormat()
        keyword.setForeground(QColor("#ff8fc7"))
        keyword.setFontWeight(QFont.Weight.DemiBold)
        words = (
            "and as assert async await break class continue def del elif else except "
            "False finally for from global if import in is lambda None nonlocal not or "
            "pass raise return True try while with yield match case"
        ).split()
        self.rules.append((re.compile(r"\b(?:" + "|".join(words) + r")\b"), keyword, 0))

        builtin = QTextCharFormat()
        builtin.setForeground(QColor("#87d7ff"))
        names = (
            "abs all any bool bytes callable chr dict dir enumerate filter float format "
            "frozenset getattr hasattr hash help hex id input int isinstance issubclass "
            "iter len list map max min next object oct open ord pow print range repr "
            "reversed round set setattr slice sorted str sum super tuple type vars zip"
        ).split()
        self.rules.append((re.compile(r"\b(?:" + "|".join(names) + r")\b"), builtin, 0))

        number = QTextCharFormat()
        number.setForeground(QColor("#c4a7ff"))
        self.rules.append((
            re.compile(r"\b(?:0[xX][0-9a-fA-F]+|0[bB][01]+|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\b"),
            number, 0,
        ))

        decorator = QTextCharFormat()
        decorator.setForeground(QColor("#ffd479"))
        self.rules.append((re.compile(r"@[A-Za-z_]\w*"), decorator, 0))

        definition = QTextCharFormat()
        definition.setForeground(QColor("#9be7b8"))
        definition.setFontWeight(QFont.Weight.DemiBold)
        self.rules.append((
            re.compile(r"\b(?:def|class)\s+([A-Za-z_]\w*)"), definition, 1
        ))

        comment = QTextCharFormat()
        comment.setForeground(QColor("#6f7a8f"))
        comment.setFontItalic(True)
        self.rules.append((re.compile(r"#.*$"), comment, 0))

        string = QTextCharFormat()
        string.setForeground(QColor("#f3c98b"))
        self.rules.append((
            re.compile(r'"""(?:.|\n)*?"""|\'\'\'(?:.|\n)*?\'\'\'|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\''),
            string, 0,
        ))

    def highlightBlock(self, text: str):  # noqa: N802
        for pattern, fmt, group in self.rules:
            for match in pattern.finditer(text):
                start, end = match.span(group)
                if end > start:
                    self.setFormat(start, end - start, fmt)


class FixWorker(QThread):
    done = Signal(str)
    error = Signal(str)

    def __init__(self, ai, code: str, traceback_text: str, parent=None):
        super().__init__(parent)
        self.ai = ai
        self.code = code
        self.traceback_text = traceback_text

    def run(self):
        system = (
            "Ты опытный Python-инженер. Исправь ошибку в коде. Верни ТОЛЬКО полный "
            "исправленный Python-код без markdown, без пояснений и без ```. "
            "Сохрани замысел программы и не добавляй сетевые запросы или опасные операции."
        )
        prompt = (
            "КОД:\n" + self.code[-14000:] + "\n\nОШИБКА:\n"
            + self.traceback_text[-6000:]
            + "\n\nВерни исправленный код целиком."
        )
        try:
            result = self.ai.complete(
                [{"role": "user", "content": prompt}], system_prompt=system
            )
        except Exception as exc:
            self.error.emit(str(exc))
            return
        result = str(result or "").strip()
        if result.startswith("```"):
            result = re.sub(r"^```(?:python)?\s*", "", result, flags=re.IGNORECASE)
            result = re.sub(r"\s*```$", "", result)
        self.done.emit(result.strip())


class FixDialog(QDialog):
    def __init__(self, proposed: str, error_text: str, parent=None):
        super().__init__(parent)
        self.result_code = ""
        self.setWindowTitle("Исправление кода локальным ИИ")
        self.resize(860, 620)
        layout = QVBoxLayout(self)
        title = QLabel("Предложенное исправление")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        info = QLabel(
            "Локальная модель предлагает новый вариант. Проверьте его перед применением: "
            "ИИ может ошибаться."
        )
        info.setObjectName("Muted")
        info.setWordWrap(True)
        layout.addWidget(info)
        self.editor = QPlainTextEdit()
        self.editor.setObjectName("CodeEditor")
        self.editor.setPlainText(proposed)
        layout.addWidget(self.editor, 1)
        details = QTextBrowser()
        details.setMaximumHeight(90)
        details.setPlainText(error_text)
        layout.addWidget(details)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("Отмена")
        cancel.setObjectName("Ghost")
        cancel.clicked.connect(self.reject)
        apply = QPushButton("Применить код")
        apply.setObjectName("Accent")
        apply.clicked.connect(self._apply)
        row.addWidget(cancel)
        row.addWidget(apply)
        layout.addLayout(row)

    def _apply(self):
        self.result_code = self.editor.toPlainText()
        self.accept()


class SandboxWorker(QThread):
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, code: str, timeout: int = 20, parent=None):
        super().__init__(parent)
        self.code = code
        self.timeout = timeout

    def run(self):
        try:
            self.done.emit(run_python(self.code, timeout=self.timeout))
        except Exception as exc:
            self.error.emit(str(exc))


class TerminalPage(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self.process: QProcess | None = None
        self.workdir = ctx.settings.access_roots()[0] if ctx.settings.access_roots() else Path.home()
        self._sandbox_worker: SandboxWorker | None = None
        self._fix_worker: FixWorker | None = None
        self._last_error = ""
        self._code_path: Path | None = None
        self._build()
        self._start_shell()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 28, 34, 26)
        layout.setSpacing(12)
        header = QHBoxLayout()
        title = QLabel("Терминал и песочница")
        title.setObjectName("PageTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.backend = QLabel("Docker: проверка…")
        self.backend.setObjectName("Tiny")
        header.addWidget(self.backend)
        layout.addLayout(header)
        warning = QLabel(
            "Терминал выполняет команды с правами вашей учётной записи. Это не песочница. "
            "Песочница Python использует Docker без сети, если он установлен; иначе — локальный Python "
            "с таймаутом, но без изоляции памяти и сети."
        )
        warning.setObjectName("Banner")
        warning.setWordWrap(True)
        warning.setStyleSheet("padding:10px 13px; color:#c9b97a;")
        layout.addWidget(warning)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        self.tabs.addTab(self._build_terminal(), "PowerShell")
        self.tabs.addTab(self._build_sandbox(), "Python-песочница")

    def _build_terminal(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(8)
        bar = QHBoxLayout()
        self.cwd_label = QLabel(str(self.workdir))
        self.cwd_label.setObjectName("Muted")
        self.cwd_label.setWordWrap(True)
        bar.addWidget(QLabel("Папка:"))
        bar.addWidget(self.cwd_label, 1)
        change = QPushButton("Сменить папку")
        change.setObjectName("Ghost")
        change.clicked.connect(self._change_dir)
        restart = QPushButton("Перезапустить")
        restart.setObjectName("Ghost")
        restart.clicked.connect(self._restart_shell)
        clear = QPushButton("Очистить")
        clear.setObjectName("Ghost")
        clear.clicked.connect(lambda: self.output.clear())
        copy = QPushButton("Копировать")
        copy.setObjectName("Ghost")
        copy.clicked.connect(lambda: self._copy(self.output.toPlainText()))
        for button in (change, restart, clear, copy):
            bar.addWidget(button)
        layout.addLayout(bar)
        self.output = QPlainTextEdit()
        self.output.setObjectName("TerminalView")
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("PowerShell…")
        layout.addWidget(self.output, 1)
        input_bar = QHBoxLayout()
        prompt = QLabel("PS ›")
        prompt.setObjectName("Accent")
        prompt.setStyleSheet("font-family:Consolas; font-weight:700;")
        input_bar.addWidget(prompt)
        self.command = HistoryLineEdit()
        self.command.setPlaceholderText("Введите команду и нажмите Enter")
        self.command.returnPressed.connect(self._send_command)
        input_bar.addWidget(self.command, 1)
        send = QPushButton("Выполнить")
        send.setObjectName("Accent")
        send.clicked.connect(self._send_command)
        input_bar.addWidget(send)
        layout.addLayout(input_bar)
        return widget

    def _build_sandbox(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(8)
        bar = QHBoxLayout()
        label = QLabel("Python 3 · временный каталог · таймаут 20 с")
        label.setObjectName("Muted")
        bar.addWidget(label, 1)
        self.open_btn = QPushButton("Открыть .py")
        self.open_btn.setObjectName("Ghost")
        self.open_btn.clicked.connect(self._open_code)
        self.save_btn = QPushButton("Сохранить .py")
        self.save_btn.setObjectName("Ghost")
        self.save_btn.clicked.connect(self._save_code)
        self.check_btn = QPushButton("Проверить синтаксис")
        self.check_btn.setObjectName("Ghost")
        self.check_btn.clicked.connect(self._check_syntax)
        self.fix_btn = QPushButton("✦  Исправить с ИИ")
        self.fix_btn.setObjectName("Ghost")
        self.fix_btn.setEnabled(False)
        self.fix_btn.clicked.connect(self._fix_with_ai)
        clear = QPushButton("Очистить")
        clear.setObjectName("Ghost")
        clear.clicked.connect(lambda: self.sandbox_output.clear())
        self.run_btn = QPushButton("▶  Запустить в песочнице")
        self.run_btn.setObjectName("Accent")
        self.run_btn.clicked.connect(self._run_sandbox)
        for button in (self.open_btn, self.save_btn, self.check_btn, self.fix_btn, clear):
            bar.addWidget(button)
        bar.addWidget(self.run_btn)
        layout.addLayout(bar)
        split = QHBoxLayout()
        self.code = QPlainTextEdit()
        self.code.setObjectName("CodeEditor")
        self.code.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.code.setPlainText(
            "import platform, sys\n\n"
            "print('Hello from AURA sandbox')\n"
            "print(platform.python_version())\n"
            "print(sys.version)\n\n"
            "for i in range(5):\n"
            "    print('step', i)\n"
        )
        self.highlighter = PythonHighlighter(self.code.document())
        self.code.textChanged.connect(self._on_code_changed)
        QShortcut(QKeySequence("Ctrl+Return"), self.code, activated=self._run_sandbox)
        QShortcut(QKeySequence("Ctrl+S"), self.code, activated=self._save_code)
        split.addWidget(self.code, 3)
        self.sandbox_output = QPlainTextEdit()
        self.sandbox_output.setObjectName("TerminalView")
        self.sandbox_output.setReadOnly(True)
        self.sandbox_output.setPlaceholderText("Здесь появится stdout и stderr…")
        split.addWidget(self.sandbox_output, 2)
        layout.addLayout(split, 1)
        self.sandbox_status = QLabel("")
        self.sandbox_status.setObjectName("Tiny")
        self.sandbox_status.setWordWrap(True)
        layout.addWidget(self.sandbox_status)
        return widget

    def _open_code(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Открыть Python-файл", str(self.workdir),
            "Python (*.py);;Все файлы (*.*)",
        )
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            QMessageBox.warning(self, "Python", f"Не удалось открыть файл:\n{exc}")
            return
        self._code_path = Path(path)
        self.code.setPlainText(text)
        self.sandbox_status.setText(f"Открыт: {path}")
        self._clear_error_highlight()
        self.fix_btn.setEnabled(False)

    def _save_code(self):
        suggested = str(self._code_path or (self.workdir / "aura_script.py"))
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить Python-файл", suggested,
            "Python (*.py);;Все файлы (*.*)",
        )
        if not path:
            return
        if not path.lower().endswith(".py"):
            path += ".py"
        try:
            Path(path).write_text(self.code.toPlainText(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Python", f"Не удалось сохранить файл:\n{exc}")
            return
        self._code_path = Path(path)
        self.sandbox_status.setText(f"Сохранено: {path}")

    def _check_syntax(self) -> bool:
        try:
            ast.parse(self.code.toPlainText())
        except SyntaxError as exc:
            line = int(exc.lineno or 1)
            self._last_error = f"SyntaxError: {exc.msg} (строка {line})"
            self._highlight_line(line)
            self.sandbox_status.setText("Синтаксическая ошибка. Можно нажать «Исправить с ИИ».")
            self.fix_btn.setEnabled(True)
            self.sandbox_output.setPlainText(self._last_error)
            return False
        self._last_error = ""
        self._clear_error_highlight()
        self.fix_btn.setEnabled(False)
        self.sandbox_status.setText("Синтаксис в порядке.")
        return True

    def _highlight_line(self, line: int):
        block = self.code.document().findBlockByNumber(max(0, int(line) - 1))
        if not block.isValid():
            return
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor("#3b1e2b"))
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        selection.cursor = QTextCursor(block)
        self.code.setExtraSelections([selection])
        self.code.setTextCursor(QTextCursor(block))
        self.code.centerCursor()

    def _clear_error_highlight(self):
        self.code.setExtraSelections([])

    def _on_code_changed(self):
        if self._last_error:
            self._last_error = ""
            self._clear_error_highlight()
            self.fix_btn.setEnabled(False)
            self.sandbox_status.setText("Код изменён. Запустите проверку или песочницу.")

    def _fix_with_ai(self):
        if self._fix_worker and self._fix_worker.isRunning():
            return
        if not self._last_error.strip():
            self.sandbox_status.setText("Сначала запустите код или проверьте синтаксис.")
            return
        self.fix_btn.setEnabled(False)
        self.run_btn.setEnabled(False)
        self.sandbox_status.setText("Локальная модель готовит исправление…")
        self._fix_worker = FixWorker(
            self.ctx.ai, self.code.toPlainText(), self._last_error, parent=self
        )
        self._fix_worker.done.connect(self._fix_done)
        self._fix_worker.error.connect(self._fix_error)
        self._fix_worker.start()

    def _fix_done(self, proposed: str):
        self.run_btn.setEnabled(True)
        self.fix_btn.setEnabled(bool(self._last_error))
        if not proposed.strip():
            self.sandbox_status.setText("ИИ вернул пустой ответ. Попробуйте другую модель.")
            return
        dialog = FixDialog(proposed, self._last_error, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_code.strip():
            self.code.setPlainText(dialog.result_code)
            self.sandbox_status.setText("Код заменён предложением локального ИИ. Проверьте его.")
            self._last_error = ""
            self._clear_error_highlight()
            self.fix_btn.setEnabled(False)
            self._check_syntax()

    def _fix_error(self, message: str):
        self.run_btn.setEnabled(True)
        self.fix_btn.setEnabled(bool(self._last_error))
        self.sandbox_status.setText("Не удалось получить исправление: " + message)

    def _start_shell(self):
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.setWorkingDirectory(str(self.workdir))
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("PYTHONUTF8", "1")
        self.process.setProcessEnvironment(env)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._shell_finished)
        self.process.errorOccurred.connect(self._shell_error)
        powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        if powershell:
            self.process.setProgram(powershell)
            self.process.setArguments([
                "-NoLogo", "-NoProfile", "-NoExit", "-ExecutionPolicy", "Bypass",
                "-Command", "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
                            "$OutputEncoding=[System.Text.Encoding]::UTF8",
            ])
            self.shell_name = "PowerShell"
        else:
            self.process.setProgram("cmd.exe")
            self.process.setArguments(["/Q"])
            self.shell_name = "cmd"
        self.process.start()
        if self.process.waitForStarted(5000):
            self._append(
                f"AURA Terminal · {self.shell_name}\n"
                f"Рабочая папка: {self.workdir}\n"
                "Команды выполняются локально. Будьте осторожны.\n\n"
            )
            self.process.write(
                ("[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
                 "$OutputEncoding=[System.Text.Encoding]::UTF8\r\n").encode("utf-8")
            )
        else:
            self._append("Не удалось запустить оболочку.\n")

    def _read_output(self):
        if not self.process:
            return
        data = self.process.readAllStandardOutput()
        text = bytes(data).decode("utf-8", "replace")
        if not text and data:
            text = bytes(data).decode("cp866", "replace")
        self._append(text)

    def _append(self, text: str):
        if not text:
            return
        self.output.moveCursor(self.output.textCursor().MoveOperation.End)
        self.output.insertPlainText(text)
        bar = self.output.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _send_command(self):
        command = self.command.text().strip()
        if not command:
            return
        if not self.process or self.process.state() != QProcess.ProcessState.Running:
            self._start_shell()
        self.command.remember(command)
        self.command.clear()
        self._append(f"\nPS {self.workdir}› {command}\n")
        if "cd " in command.lower() and self.process:
            candidate = command.split(maxsplit=1)[1].strip().strip('"')
            candidate_path = Path(candidate)
            if not candidate_path.is_absolute():
                candidate_path = self.workdir / candidate_path
            if candidate_path.exists():
                self.workdir = candidate_path.resolve()
                self.cwd_label.setText(str(self.workdir))
                self.process.setWorkingDirectory(str(self.workdir))
        self.process.write((command + "\r\n").encode("utf-8"))
        self.process.waitForBytesWritten(1000)

    def _change_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Рабочая папка", str(self.workdir))
        if folder:
            self.workdir = Path(folder)
            self.cwd_label.setText(str(self.workdir))
            if self.process:
                self.process.setWorkingDirectory(str(self.workdir))
            self._append(f"\nРабочая папка: {self.workdir}\n")

    def _restart_shell(self):
        if self.process:
            self.process.kill()
            self.process.waitForFinished(1500)
        self.output.clear()
        self._start_shell()

    def _shell_finished(self, code, status):
        self._append(f"\n[оболочка завершена, код {code}]\n")

    def _shell_error(self, error):
        self._append(f"\n[ошибка процесса: {error}]\n")

    def _copy(self, text: str):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)

    def _run_sandbox(self):
        if self._sandbox_worker and self._sandbox_worker.isRunning():
            return
        code = self.code.toPlainText()
        if not code.strip():
            return
        self._last_error = ""
        self._clear_error_highlight()
        self.fix_btn.setEnabled(False)
        self.run_btn.setEnabled(False)
        self.sandbox_output.setPlainText("Выполняется…")
        self.sandbox_status.setText("Запуск…")
        self._sandbox_worker = SandboxWorker(code, timeout=20, parent=self)
        self._sandbox_worker.done.connect(self._sandbox_done)
        self._sandbox_worker.error.connect(self._sandbox_error)
        self._sandbox_worker.start()

    def _sandbox_done(self, result: dict):
        self.run_btn.setEnabled(True)
        backend = result.get("backend", "local")
        self.backend.setText(f"Последний запуск: {backend}")
        parts = []
        if result.get("stdout"):
            parts.append(result["stdout"])
        stderr = str(result.get("stderr") or "")
        if stderr:
            parts.append("[stderr]\n" + stderr)
        if not parts:
            parts.append("(нет вывода)")
        parts.append(f"\n[exit {result.get('exit_code')}, backend: {backend}]")
        self.sandbox_output.setPlainText("\n".join(parts))
        exit_code = result.get("exit_code")
        if stderr.strip() or (exit_code not in (0, None)):
            self._last_error = stderr.strip() or f"Процесс завершился с кодом {exit_code}."
            match = re.search(r'line (\d+)', stderr)
            if match:
                self._highlight_line(int(match.group(1)))
            warning = str(result.get("warning") or "").strip()
            self.sandbox_status.setText(
                (warning + " " if warning else "")
                + "Ошибка. Нажмите «Исправить с ИИ», чтобы предложить исправление."
            )
            self.fix_btn.setEnabled(True)
        else:
            self._last_error = ""
            self._clear_error_highlight()
            self.fix_btn.setEnabled(False)
            self.sandbox_status.setText(result.get("warning") or "Код выполнен без ошибок.")

    def _sandbox_error(self, message: str):
        self.run_btn.setEnabled(True)
        self._last_error = message
        self.sandbox_output.setPlainText("Ошибка:\n" + message)
        self.sandbox_status.setText("Песочница завершилась с ошибкой. Доступно исправление ИИ.")
        self.fix_btn.setEnabled(True)

    def showEvent(self, event):  # noqa: N802
        self.backend.setText(
            "Docker доступен" if docker_available() else "Docker не найден · локальный режим"
        )
        super().showEvent(event)

    def shutdown(self):
        if self.process:
            self.process.kill()
            self.process.waitForFinished(1000)
        if self._sandbox_worker and self._sandbox_worker.isRunning():
            self._sandbox_worker.wait(2000)
        if self._fix_worker and self._fix_worker.isRunning():
            self._fix_worker.wait(2000)
