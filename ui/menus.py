"""Context menus shared by music pages."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QInputDialog, QMenu, QMessageBox

from core.db import Database
from core.player import PlayerController


def show_track_menu(parent, track: dict, db: Database, player: PlayerController,
                    playlist_id: int | None = None, on_changed=None):
    menu = QMenu(parent)
    menu.addAction("▶  Играть", lambda: player.play_track(track))
    menu.addAction("Играть следующим", lambda: player.add_to_queue(track, next_item=True))
    menu.addAction("В очередь", lambda: player.add_to_queue(track, next_item=False))
    menu.addSeparator()
    favorite = bool(track.get("favorite"))
    menu.addAction("Убрать из любимых" if favorite else "♡  В любимые",
                   lambda: player.toggle_favorite(track))
    add_menu = menu.addMenu("Добавить в плейлист")
    playlists = db.playlists()
    if playlists:
        for playlist in playlists:
            add_menu.addAction(
                str(playlist["name"]),
                lambda pid=playlist["id"]: (db.add_to_playlist(int(pid), int(track["id"])),
                                            on_changed and on_changed()),
            )
    else:
        add_menu.addAction("Нет плейлистов").setEnabled(False)
    add_menu.addSeparator()
    add_menu.addAction("Создать новый…", lambda: _create_playlist(parent, db, track, on_changed))
    if playlist_id:
        menu.addAction("Убрать из этого плейлиста",
                       lambda: (db.remove_from_playlist(playlist_id, int(track["id"])),
                                on_changed and on_changed()))
    menu.addSeparator()
    if track.get("is_local", True):
        file_path = Path(str(track.get("path") or ""))
        menu.addAction("Открыть папку с файлом",
                       lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(file_path.parent))))
        menu.addAction("Скопировать путь", lambda: _copy(parent, str(file_path)))
    elif track.get("external_url"):
        menu.addAction("Открыть внешнюю ссылку в браузере",
                       lambda: QDesktopServices.openUrl(QUrl(str(track["external_url"]))))
    menu.exec(parent.cursor().pos())


def _copy(parent, text: str):
    from PySide6.QtWidgets import QApplication
    QApplication.clipboard().setText(text)


def _create_playlist(parent, db: Database, track: dict, on_changed=None):
    name, ok = QInputDialog.getText(parent, "Новый плейлист", "Название:")
    if not ok or not name.strip():
        return
    playlist_id = db.create_playlist(name.strip())
    db.add_to_playlist(playlist_id, int(track["id"]))
    if on_changed:
        on_changed()
    QMessageBox.information(parent, "AURA", f"Плейлист «{name.strip()}» создан.")
