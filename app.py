"""AURA Studio entry point."""
from __future__ import annotations

import argparse
import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler


def setup_logging(log_dir):
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler = RotatingFileHandler(
        log_dir / "aura.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


def run_media_selftest(ctx) -> int:
    """Exercise bundled media/voice libraries without using the network."""
    import json
    import time
    from core import media_studio
    from core.config import DATA_DIR
    from core.voice import vosk_installed, vosk_model_path

    result = {"ok": False, "started": time.strftime("%Y-%m-%dT%H:%M:%S")}
    try:
        import lxml  # noqa: F401
        import numpy  # noqa: F401
        import pyaudio  # noqa: F401
        import pyttsx3  # noqa: F401
        import vosk  # noqa: F401
        from PIL import Image  # noqa: F401
        import imageio_ffmpeg
        import pptx  # noqa: F401

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        result["ffmpeg"] = bool(ffmpeg and os.path.isfile(ffmpeg))
        result["vosk_model"] = str(vosk_model_path()) if vosk_installed() else ""

        wav = DATA_DIR / "smoke-tts.wav"
        ctx.tts.save_wav("AURA проверяет локальную озвучку.", wav)
        result["tts_bytes"] = wav.stat().st_size

        deck = media_studio.generate_presentation(
            "AURA packaged self-test", audience="test", slides=4,
            use_ai=False, with_images=False,
        )
        result["pptx"] = deck["path"]
        result["pptx_bytes"] = deck["bytes"]

        video = media_studio.generate_video(
            "AURA packaged self-test", image_count=2, seconds_per_image=1.0,
            width=640, height=360, use_ai_images=False, use_demo_music=False,
        )
        result["mp4"] = video["path"]
        result["mp4_bytes"] = video["bytes"]
        result["ok"] = True
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        path = DATA_DIR / "smoke-media.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("AURA_MEDIA_SMOKE " + json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="AURA Studio")
    parser.add_argument("--smoke-test", action="store_true", help="Start headless and exit")
    parser.add_argument("--smoke-media", action="store_true", help="Exercise packaged media/voice modules and exit")
    parser.add_argument("--data-dir", default="", help="Override user data directory")
    args, qt_args = parser.parse_known_args()
    if args.data_dir:
        os.environ["AURA_DATA_DIR"] = os.path.abspath(args.data_dir)
    if args.smoke_test or args.smoke_media:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    # Import after applying --data-dir: core.config resolves the data directory
    # from AURA_DATA_DIR at import time.
    from core.config import APP_NAME, APP_VERSION

    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

    from core.agents import AgentManager
    from core.ai import AIClient
    from core.auth import AuthManager
    from core.config import DATA_DIR, LOG_DIR, ensure_directories, resource_path
    from core.db import Database
    from core.local_ai import OllamaManager
    from core.player import PlayerController
    from core.plugins import PluginManager
    from core.access import AccessPolicy
    from core.server import AuraServer
    from core.tools import ToolRegistry
    from core.voice import SpeechRecognizer, TTSService, VoiceCommandRouter
    from ui.auth_dialog import AuthDialog, WorkspaceDialog
    from ui.context import AppContext, AppEvents
    from ui.main_window import MainWindow
    from ui.theme import apply_theme

    ensure_directories()
    setup_logging(LOG_DIR)
    logging.getLogger(__name__).info("Starting AURA Studio %s", APP_VERSION)

    app = QApplication([sys.argv[0], *qt_args])
    app.setApplicationName(APP_NAME)
    # Do not set applicationDisplayName: Qt appends it to every top-level
    # window title on Windows, which produced "AURA Studio <version> - AURA Studio".
    app.setOrganizationName("AURA")
    app.setApplicationVersion(APP_VERSION)
    icon_path = resource_path("assets", "aura.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    apply_theme(app, "sunset")

    def exception_hook(exc_type, exc_value, exc_tb):
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logging.getLogger("aura").critical("Unhandled exception:\n%s", text)
        try:
            QMessageBox.critical(
                None, "AURA — ошибка",
                "Произошла непредвиденная ошибка. Подробности записаны в журнал.\n\n"
                + str(exc_value),
            )
        except Exception:
            pass

    sys.excepthook = exception_hook

    settings = None
    db = None
    window = None
    auth = None
    user = None
    workspace = "player"
    try:
        settings = __import__("core.config", fromlist=["get_settings"]).get_settings()
        apply_theme(app, str(settings.get("ui.accent", "sunset")))
        if not args.smoke_test and not args.smoke_media:
            auth = AuthManager()
            login = AuthDialog(auth, settings)
            if login.exec() != QDialog.DialogCode.Accepted:
                return 0
            user = login.user
            picker = WorkspaceDialog(user, settings)
            if picker.exec() == QDialog.DialogCode.Accepted:
                workspace = picker.workspace
        db = Database()
        agents = AgentManager(settings)
        policy = AccessPolicy(
            settings.access_roots(),
            allow_write=bool(settings.get("access.allow_write", False)),
            allow_shell=bool(settings.get("access.allow_shell", False)),
            allow_network=bool(settings.get("access.allow_network", True)),
            allow_system=bool(settings.get("access.allow_system", False)),
        )
        plugins = PluginManager(settings, db, policy)
        tools = ToolRegistry(settings, db, plugins)
        player = PlayerController(db, int(settings.get("ui.volume", 72)))
        player.set_shuffle(bool(settings.get("ui.shuffle", False)))
        player.set_repeat(str(settings.get("ui.repeat", "off")))
        ai = AIClient(settings, agents, tools)
        server = AuraServer(settings, db, ai, agents, tools)
        events = AppEvents()
        tts = TTSService(settings)
        recognizer = SpeechRecognizer(settings)
        local_ai = OllamaManager(settings)
        ctx = AppContext(
            settings=settings, db=db, player=player, agents=agents,
            plugins=plugins, tools=tools, ai=ai, server=server, events=events,
            tts=tts, recognizer=recognizer, local_ai=local_ai,
        )
        ctx.voice_router = VoiceCommandRouter(ctx, tts)
        if args.smoke_media:
            code = run_media_selftest(ctx)
            try:
                db.close()
            except Exception:
                pass
            return code
        apply_theme(app, str(settings.get("ui.accent", "sunset")))
        window = MainWindow(
            ctx, user=user, auth=auth, start_workspace=workspace
        )
        window.show()
        if args.smoke_test:
            app.processEvents()
            QTimer.singleShot(250, app.quit)
            app.exec()
            window.close()
            print("AURA_SMOKE_OK")
            return 0
        return app.exec()
    except Exception:
        logging.exception("Startup failed")
        try:
            QMessageBox.critical(None, "AURA", "Не удалось запустить приложение.\n\n" + traceback.format_exc(limit=3))
        except Exception:
            pass
        return 1
    finally:
        if window is not None:
            try:
                window.close()
            except Exception:
                pass
        if auth is not None:
            try:
                auth.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
