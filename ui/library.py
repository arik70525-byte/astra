"""Library page: tracks, albums, playlists, scanning and imports."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QInputDialog, QLabel, QListWidget, QListWidgetItem, QMessageBox,
    QProgressDialog, QPushButton, QScrollArea, QSizePolicy, QTabWidget,
    QVBoxLayout, QWidget,
)

from core.demo_music import generate_demo_pack, import_audio_files
from core.playlists_io import export_csv, export_json, export_m3u, import_playlist_file
from core.scan import scan_library
from ui.components import MediaCard, TrackTable, clear_layout
from ui.context import AppContext
from ui.menus import show_track_menu


class ScanWorker(QThread):
    progress = Signal(int, int, str)
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, db, folders, parent=None):
        super().__init__(parent)
        self.db = db
        self.folders = folders
        self.cancelled = False

    def run(self):
        try:
            result = scan_library(
                self.db, self.folders,
                progress=lambda i, total, name: self.progress.emit(i, total, name),
                should_cancel=lambda: self.cancelled,
                remove_missing=False,
            )
            self.done.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class DemoPackWorker(QThread):
    progress = Signal(int, int, str)
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, settings, db, *, force: bool = False, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.db = db
        self.force = force
        self.cancelled = False

    def run(self):
        try:
            result = generate_demo_pack(
                self.db, self.settings, force=self.force,
                progress=lambda i, total, name: self.progress.emit(i, total, name),
                cancelled=lambda: self.cancelled,
            )
            self.done.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class AudioImportWorker(QThread):
    progress = Signal(int, int, str)
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, settings, db, files, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.db = db
        self.files = list(files)
        self.cancelled = False

    def run(self):
        try:
            result = import_audio_files(
                self.db, self.settings, self.files,
                progress=lambda i, total, name: self.progress.emit(i, total, name),
                cancelled=lambda: self.cancelled,
            )
            self.done.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class AlbumDialog(QDialog):
    def __init__(self, ctx: AppContext, album: str, artist: str, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle(f"{album} — {artist}")
        self.resize(920, 620)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        title = QLabel(album or "Без альбома")
        title.setObjectName("PageTitle")
        subtitle = QLabel(artist or "")
        subtitle.setObjectName("Muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        tracks = ctx.db.album_tracks(album, artist)
        table = TrackTable()
        table.set_tracks(tracks)
        table.play_requested.connect(ctx.player.play_track)
        table.favorite_requested.connect(ctx.player.toggle_favorite)
        table.menu_requested.connect(lambda track, point: show_track_menu(self, track, ctx.db, ctx.player))
        layout.addWidget(table, 1)
        play_all = QPushButton("▶  Играть весь альбом")
        play_all.setObjectName("Accent")
        play_all.clicked.connect(lambda: ctx.player.play_tracks(tracks, 0))
        layout.addWidget(play_all, alignment=Qt.AlignmentFlag.AlignLeft)


class LibraryPage(QWidget):
    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self._scan_worker: ScanWorker | None = None
        self._demo_worker: DemoPackWorker | None = None
        self._import_worker: AudioImportWorker | None = None
        self._current_tracks: list[dict] = []
        self._current_playlist_id: int | None = None
        self._build()
        ctx.events.library_changed.connect(self.refresh)
        ctx.player.favorite_changed.connect(self._favorite_changed)
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(34, 28, 34, 26)
        root.setSpacing(14)
        header = QHBoxLayout()
        head_text = QVBoxLayout()
        title = QLabel("Коллекция")
        title.setObjectName("PageTitle")
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("Muted")
        head_text.addWidget(title)
        head_text.addWidget(self.subtitle)
        header.addLayout(head_text)
        header.addStretch(1)
        self.demo_btn = QPushButton("✦  Демо-альбом")
        self.demo_btn.setObjectName("Ghost")
        self.demo_btn.setToolTip("Сгенерировать 6 оригинальных синтезированных треков AURA")
        self.demo_btn.clicked.connect(self.generate_demo)
        files_btn = QPushButton("＋ Аудиофайлы")
        files_btn.clicked.connect(self.import_audio)
        add_btn = QPushButton("Папка")
        add_btn.clicked.connect(self.add_folder)
        import_btn = QPushButton("Плейлист")
        import_btn.clicked.connect(self.import_playlist)
        self.sync_btn = QPushButton("Синхронизация…")
        self.sync_btn.setObjectName("Ghost")
        self.sync_btn.clicked.connect(self.playlist_sync_info)
        self.scan_btn = QPushButton("↻  Сканировать")
        self.scan_btn.setObjectName("Accent")
        self.scan_btn.clicked.connect(self.scan)
        for button in (self.demo_btn, files_btn, add_btn, import_btn, self.sync_btn, self.scan_btn):
            header.addWidget(button)
        root.addLayout(header)

        toolbar = QHBoxLayout()
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Недавно добавленные", "added")
        self.sort_combo.addItem("По названию", "title")
        self.sort_combo.addItem("По исполнителю", "artist")
        self.sort_combo.addItem("По прослушиваниям", "plays")
        self.sort_combo.currentIndexChanged.connect(self._load_tracks_tab)
        toolbar.addWidget(self.sort_combo)
        toolbar.addStretch(1)
        export_btn = QPushButton("Экспорт M3U / CSV / JSON")
        export_btn.setObjectName("Ghost")
        export_btn.clicked.connect(self.export_current)
        toolbar.addWidget(export_btn)
        self.status = QLabel("")
        self.status.setObjectName("Tiny")
        toolbar.addWidget(self.status)
        root.addLayout(toolbar)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self.tracks_table = TrackTable()
        self.tracks_table.play_requested.connect(self.ctx.player.play_track)
        self.tracks_table.favorite_requested.connect(self.ctx.player.toggle_favorite)
        self.tracks_table.menu_requested.connect(self._track_menu)
        self.tabs.addTab(self.tracks_table, "Треки")

        albums_widget = QWidget()
        albums_layout = QVBoxLayout(albums_widget)
        albums_layout.setContentsMargins(0, 10, 0, 0)
        self.albums_scroll = QScrollArea()
        self.albums_scroll.setWidgetResizable(True)
        self.albums_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.albums_inner = QWidget()
        self.albums_grid = QGridLayout(self.albums_inner)
        self.albums_grid.setContentsMargins(0, 0, 0, 0)
        self.albums_grid.setSpacing(10)
        self.albums_scroll.setWidget(self.albums_inner)
        albums_layout.addWidget(self.albums_scroll)
        self.tabs.addTab(albums_widget, "Альбомы")

        playlists_widget = QWidget()
        playlists_layout = QHBoxLayout(playlists_widget)
        playlists_layout.setContentsMargins(0, 10, 0, 0)
        playlists_layout.setSpacing(14)
        left = QVBoxLayout()
        self.playlist_list = QListWidget()
        self.playlist_list.setMinimumWidth(230)
        self.playlist_list.currentItemChanged.connect(self._playlist_selected)
        left.addWidget(self.playlist_list, 1)
        pl_buttons = QHBoxLayout()
        new_btn = QPushButton("＋")
        new_btn.setToolTip("Создать плейлист")
        new_btn.clicked.connect(self.create_playlist)
        rename_btn = QPushButton("✎")
        rename_btn.setToolTip("Переименовать")
        rename_btn.clicked.connect(self.rename_playlist)
        delete_btn = QPushButton("🗑")
        delete_btn.setToolTip("Удалить")
        delete_btn.clicked.connect(self.delete_playlist)
        for button in (new_btn, rename_btn, delete_btn):
            button.setFixedWidth(42)
            pl_buttons.addWidget(button)
        pl_buttons.addStretch(1)
        left.addLayout(pl_buttons)
        playlists_layout.addLayout(left)
        right = QVBoxLayout()
        self.playlist_title = QLabel("Выберите плейлист")
        self.playlist_title.setObjectName("SectionTitle")
        right.addWidget(self.playlist_title)
        self.playlist_table = TrackTable()
        self.playlist_table.play_requested.connect(self.ctx.player.play_track)
        self.playlist_table.favorite_requested.connect(self.ctx.player.toggle_favorite)
        self.playlist_table.menu_requested.connect(self._playlist_menu)
        right.addWidget(self.playlist_table, 1)
        playlists_layout.addLayout(right, 1)
        self.tabs.addTab(playlists_widget, "Плейлисты")

        self.liked_table = TrackTable()
        self.liked_table.play_requested.connect(self.ctx.player.play_track)
        self.liked_table.favorite_requested.connect(self.ctx.player.toggle_favorite)
        self.liked_table.menu_requested.connect(self._track_menu)
        self.tabs.addTab(self.liked_table, "Любимое")

        self.tabs.currentChanged.connect(self._tab_changed)

    def refresh(self):
        stats = self.ctx.db.stats()
        folders = ", ".join(str(p) for p in self.ctx.settings.library_folders())
        self.subtitle.setText(
            f"{stats['tracks']} треков · {stats['albums']} альбомов · {stats['artists']} исполнителей"
            + (f" · {folders}" if folders else " · папки не выбраны")
        )
        self.demo_btn.setEnabled(not (self._demo_worker and self._demo_worker.isRunning()))
        self._load_tracks_tab()
        self._load_albums()
        self._load_playlists()
        self.liked_table.set_tracks(self.ctx.db.favorite_tracks(limit=500))

    def _load_tracks_tab(self):
        order = self.sort_combo.currentData() or "added"
        tracks = self.ctx.db.tracks(limit=1000, order=order)
        self._current_tracks = tracks
        self.tracks_table.set_tracks(tracks)
        self.status.setText(f"{len(tracks)} показано")

    def _load_albums(self):
        clear_layout(self.albums_grid)
        albums = self.ctx.db.albums(limit=200)
        for index, album in enumerate(albums):
            card = MediaCard(
                title=album.get("album") or "Без альбома",
                subtitle=f"{album.get('artist') or ''} · {album.get('track_count')} треков",
                cover=album.get("cover_path"),
                data=album,
            )
            card.clicked.connect(self._open_album)
            self.albums_grid.addWidget(card, index // 5, index % 5)
        if not albums:
            label = QLabel("Альбомы появятся после сканирования папки с музыкой.")
            label.setObjectName("Muted")
            self.albums_grid.addWidget(label, 0, 0)
        self.albums_grid.setRowStretch(len(albums) // 5 + 1, 1)

    def _load_playlists(self):
        selected = self._current_playlist_id
        self.playlist_list.blockSignals(True)
        self.playlist_list.clear()
        for playlist in self.ctx.db.playlists():
            item = QListWidgetItem(f"♫  {playlist['name']}  ·  {playlist['track_count']}")
            item.setData(Qt.ItemDataRole.UserRole, playlist)
            self.playlist_list.addItem(item)
        self.playlist_list.blockSignals(False)
        if selected is not None:
            for index in range(self.playlist_list.count()):
                item = self.playlist_list.item(index)
                data = item.data(Qt.ItemDataRole.UserRole)
                if data and int(data["id"]) == int(selected):
                    self.playlist_list.setCurrentItem(item)
                    break

    def _tab_changed(self, index: int):
        if index == 3:
            self.liked_table.set_tracks(self.ctx.db.favorite_tracks(limit=500))
        elif index == 2:
            self._load_playlists()
        elif index == 1:
            self._load_albums()

    def _open_album(self, album: dict):
        dialog = AlbumDialog(
            self.ctx, str(album.get("album") or ""), str(album.get("artist") or ""), self
        )
        dialog.exec()

    def _track_menu(self, track: dict, point):
        show_track_menu(self, track, self.ctx.db, self.ctx.player,
                        on_changed=lambda: self.ctx.events.library_changed.emit())

    def _playlist_menu(self, track: dict, point):
        show_track_menu(self, track, self.ctx.db, self.ctx.player,
                        playlist_id=self._current_playlist_id, on_changed=self._reload_playlist)

    def _playlist_selected(self, current: QListWidgetItem | None, previous=None):
        if current is None:
            return
        playlist = current.data(Qt.ItemDataRole.UserRole)
        if not playlist:
            return
        self._current_playlist_id = int(playlist["id"])
        self.playlist_title.setText(
            f"{playlist['name']}  ·  {playlist.get('track_count', 0)} треков"
        )
        tracks = self.ctx.db.playlist_tracks(self._current_playlist_id)
        self.playlist_table.set_tracks(tracks)
        self._current_tracks = tracks

    def _reload_playlist(self):
        if self._current_playlist_id is not None:
            self._load_playlists()
            for row in range(self.playlist_list.count()):
                item = self.playlist_list.item(row)
                data = item.data(Qt.ItemDataRole.UserRole)
                if data and int(data["id"]) == int(self._current_playlist_id):
                    self._playlist_selected(item)
                    break

    def create_playlist(self):
        name, ok = QInputDialog.getText(self, "Новый плейлист", "Название:")
        if ok and name.strip():
            self.ctx.db.create_playlist(name.strip())
            self._load_playlists()
            self.tabs.setCurrentIndex(2)

    def rename_playlist(self):
        if self._current_playlist_id is None:
            return
        name, ok = QInputDialog.getText(self, "Переименовать", "Новое название:")
        if ok and name.strip():
            self.ctx.db.rename_playlist(self._current_playlist_id, name.strip())
            self._load_playlists()

    def delete_playlist(self):
        if self._current_playlist_id is None:
            return
        if QMessageBox.question(
            self, "Удалить плейлист",
            "Удалить плейлист? Треки останутся в медиатеке.",
        ) == QMessageBox.StandardButton.Yes:
            self.ctx.db.delete_playlist(self._current_playlist_id)
            self._current_playlist_id = None
            self.playlist_title.setText("Выберите плейлист")
            self.playlist_table.set_tracks([])
            self._load_playlists()

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Добавить папку с музыкой")
        if not folder:
            return
        folders = list(self.ctx.settings.get("library.folders", []) or [])
        if folder not in folders:
            folders.append(folder)
            self.ctx.settings.set("library.folders", folders)
            self.ctx.settings.save()
            self.ctx.events.settings_changed.emit()
            self.ctx.events.toast.emit("Папка добавлена. Начинаю сканирование…")
            self.scan()

    def scan(self):
        if self._scan_worker and self._scan_worker.isRunning():
            return
        folders = self.ctx.settings.library_folders()
        if not folders:
            if QMessageBox.question(
                self, "Нет папок", "Добавить папку с музыкой сейчас?"
            ) == QMessageBox.StandardButton.Yes:
                self.add_folder()
            return
        dialog = QProgressDialog("Сканирование медиатеки…", "Отмена", 0, 100, self)
        dialog.setWindowTitle("AURA · Сканирование")
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(300)
        worker = ScanWorker(self.ctx.db, folders, self)
        self._scan_worker = worker
        last = [0]

        def on_progress(index, total, name):
            if total:
                percent = int(index * 100 / total)
                dialog.setValue(percent)
                dialog.setLabelText(f"{index}/{total}\n{name}")

        def on_done(result):
            dialog.close()
            self.ctx.events.library_changed.emit()
            self.refresh()
            self.ctx.events.toast.emit(
                f"Сканирование завершено: +{result.get('added', 0)}, "
                f"обновлено {result.get('updated', 0)}, ошибок {result.get('errors', 0)}"
            )
            QMessageBox.information(
                self, "Сканирование завершено",
                f"Добавлено: {result.get('added', 0)}\n"
                f"Обновлено: {result.get('updated', 0)}\n"
                f"Ошибок: {result.get('errors', 0)}",
            )

        def on_error(message):
            dialog.close()
            QMessageBox.critical(self, "Ошибка сканирования", message)

        worker.progress.connect(on_progress)
        worker.done.connect(on_done)
        worker.error.connect(on_error)
        dialog.canceled.connect(lambda: setattr(worker, "cancelled", True))
        worker.start()
        dialog.show()

    def import_playlist(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Импорт плейлиста", "",
            "Плейлисты (*.m3u *.m3u8 *.csv *.json);;Все файлы (*.*)",
        )
        if not path:
            return
        try:
            result = import_playlist_file(self.ctx.db, Path(path))
            self.ctx.events.library_changed.emit()
            self.refresh()
            self._load_playlists()
            self.tabs.setCurrentIndex(2)
            QMessageBox.information(
                self, "Импорт завершён",
                f"Плейлист «{result['name']}»: добавлено {result['tracks']} треков.\n\n"
                "Для Яндекс Музыки используйте экспорт плейлиста в M3U/CSV и импорт этого файла — "
                "официального API для сторонних плееров у Яндекс Музыки нет.",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка импорта", str(exc))

    def generate_demo(self):
        if self._demo_worker and self._demo_worker.isRunning():
            self.ctx.events.toast.emit("Демо-альбом уже генерируется…")
            return
        dialog = QProgressDialog("Генерирую оригинальные треки AURA…", "Отмена", 0, 100, self)
        dialog.setWindowTitle("AURA · Демо-альбом")
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(200)
        worker = DemoPackWorker(self.ctx.settings, self.ctx.db, parent=self)
        self._demo_worker = worker
        self.demo_btn.setEnabled(False)

        def on_progress(index, total, name):
            if total:
                dialog.setValue(int(index * 100 / total))
                dialog.setLabelText(f"{index}/{total}\n{name}")

        def on_done(result):
            dialog.close()
            self.demo_btn.setEnabled(True)
            self.ctx.events.library_changed.emit()
            self.refresh()
            errors = result.get("errors") or []
            QMessageBox.information(
                self, "Демо-альбом готов",
                f"Добавлено треков: {result.get('created', 0)}\n"
                f"Обновлено: {result.get('updated', 0)}\n"
                f"Плейлист: AURA Originals · Demo\n\n"
                + ("Замечания:\n" + "\n".join(errors[:5]) if errors else
                   "Все треки синтезированы локально из оригинальных нот AURA."),
            )

        def on_error(message):
            dialog.close()
            self.demo_btn.setEnabled(True)
            QMessageBox.critical(self, "Демо-альбом", message)

        worker.progress.connect(on_progress)
        worker.done.connect(on_done)
        worker.error.connect(on_error)
        dialog.canceled.connect(lambda: setattr(worker, "cancelled", True))
        worker.start()
        dialog.show()

    def import_audio(self):
        if self._import_worker and self._import_worker.isRunning():
            return
        files, _ = QFileDialog.getOpenFileNames(
            self, "Добавить аудиофайлы", "",
            "Аудио (*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.opus *.wma);;Все файлы (*.*)",
        )
        if not files:
            return
        dialog = QProgressDialog("Копирую и индексирую аудио…", "Отмена", 0, len(files), self)
        dialog.setWindowTitle("AURA · Импорт аудио")
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(200)
        worker = AudioImportWorker(self.ctx.settings, self.ctx.db, files, self)
        self._import_worker = worker

        def on_progress(index, total, name):
            dialog.setMaximum(max(1, total))
            dialog.setValue(index)
            dialog.setLabelText(f"{index}/{total}\n{name}")

        def on_done(result):
            dialog.close()
            self.ctx.events.library_changed.emit()
            self.refresh()
            self._load_playlists()
            details = result.get("details") or []
            QMessageBox.information(
                self, "Импорт аудио",
                f"Добавлено: {result.get('added', 0)}\n"
                f"Обновлено: {result.get('updated', 0)}\n"
                f"Ошибок: {result.get('errors', 0)}"
                + ("\n\n" + "\n".join(details[:6]) if details else ""),
            )

        def on_error(message):
            dialog.close()
            QMessageBox.critical(self, "Импорт аудио", message)

        worker.progress.connect(on_progress)
        worker.done.connect(on_done)
        worker.error.connect(on_error)
        dialog.canceled.connect(lambda: setattr(worker, "cancelled", True))
        worker.start()
        dialog.show()

    def playlist_sync_info(self):
        box = QMessageBox(self)
        box.setWindowTitle("Синхронизация плейлистов")
        box.setIcon(QMessageBox.Icon.Information)
        box.setText("Честная синхронизация через файлы")
        box.setInformativeText(
            "AURA умеет экспортировать текущий плейлист в M3U/CSV и импортировать "
            "M3U/M3U8/CSV/JSON. Это работает с Spotify, Яндекс Музыкой, VLC, foobar2000 "
            "и другими плеерами без API-ключей.\n\n"
            "Ограничения сервисов:\n"
            "• Spotify: AURA не подключает облачный аккаунт и не скачивает потоки; "
            "используйте файл плейлиста или внешнюю ссылку.\n"
            "• Яндекс Музыка: официального API для сторонних плееров нет; используйте "
            "экспорт/импорт файла из поддерживаемого клиента.\n\n"
            "AURA не подключается к неофициальным API и не обходит ограничения сервисов."
        )
        export_button = box.addButton("Экспорт текущего", QMessageBox.ButtonRole.ActionRole)
        import_button = box.addButton("Импорт файла", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Закрыть", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is export_button:
            self.export_current()
        elif box.clickedButton() is import_button:
            self.import_playlist()

    def export_current(self):
        tracks = self._current_tracks
        if not tracks:
            QMessageBox.information(self, "Экспорт", "Нет треков для экспорта.")
            return
        path, selected = QFileDialog.getSaveFileName(
            self, "Экспорт плейлиста", "aura_playlist.m3u",
            "M3U (*.m3u);;CSV (*.csv);;JSON для Android (*.json)",
        )
        if not path:
            return
        try:
            if selected.startswith("CSV") or path.lower().endswith(".csv"):
                export_csv(Path(path), tracks)
            elif selected.startswith("JSON") or path.lower().endswith(".json"):
                export_json(Path(path), tracks, title="AURA Studio")
            else:
                export_m3u(Path(path), tracks, title="AURA Studio")
            QMessageBox.information(self, "Экспорт", f"Сохранено:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка экспорта", str(exc))

    def _favorite_changed(self, track_id: int, value: bool):
        self.tracks_table.update_favorite(track_id, value)
        self.liked_table.update_favorite(track_id, value)
        self.playlist_table.update_favorite(track_id, value)
