"""Shared application context and event bus."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, Signal

from core.agents import AgentManager
from core.ai import AIClient
from core.config import Settings
from core.db import Database
from core.player import PlayerController
from core.plugins import PluginManager
from core.server import AuraServer
from core.tools import ToolRegistry


class AppEvents(QObject):
    library_changed = Signal()
    settings_changed = Signal()
    toast = Signal(str)
    open_settings = Signal()
    open_chat = Signal(str)  # agent id
    play_tracks = Signal(object)
    navigate = Signal(str)  # page key
    voice_prompt = Signal(str)  # send a prompt to the AI chat
    ask_ai = Signal(str)  # insert a prompt into the AI chat without sending
    voice_listen = Signal()  # global hotkey / external request
    accent_changed = Signal(str)


@dataclass
class AppContext:
    settings: Settings
    db: Database
    player: PlayerController
    agents: AgentManager
    plugins: PluginManager
    tools: ToolRegistry
    ai: AIClient
    server: AuraServer
    events: AppEvents
    # Voice/local-AI services are attached after the dataclass is built because
    # the voice router itself needs the complete context.
    tts: Any = None
    recognizer: Any = None
    local_ai: Any = None
    voice_router: Any = None
