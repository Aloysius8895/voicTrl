"""Turns an utterance heard by the watch into user input for the voice
assistant, and decides what the watch should show in return."""

from __future__ import annotations

import logging
import re
from collections import deque
import time
from typing import Callable

from pagent.coordinator.agora import AgoraClient, AgoraError
from pagent.coordinator.voice import VoiceSessions
from pagent.protocol import AgentTranscript, Display, Utterance


log = logging.getLogger(__name__)

MIN_WORDS = 2
# Shorter utterances are usually noise ("uh"), but these answer the assistant.
SINGLE_WORD_COMMANDS = {"confirm", "yes", "cancel"}
_PUNCT = re.compile(r"[^\w\s]")
# A word is a run of non-space characters, except that each CJK character counts
# on its own (Chinese has no spaces between words).
_WORD = re.compile(r"[一-鿿]|[^\s一-鿿]+")
DEDUP_WINDOW_S = 3.0
# Agora documents no length limit for /think text (05 research, A3). 8 KiB of
# UTF-8 is the cap Agora's own voice-coder recipe uses, so we stay within it.
MAX_TEXT_BYTES = 8 * 1024
NO_SESSION = Display(title="Open the voice page on your phone", vibrate=True)
AGORA_FAILED = Display(title="Voice assistant error", body="Please say it again", vibrate=True)


class UtteranceRelay:
    def __init__(
        self,
        agora: AgoraClient,
        sessions: VoiceSessions,
        *,
        max_text_bytes: int = MAX_TEXT_BYTES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._agora = agora
        self._sessions = sessions
        self._max_text_bytes = max_text_bytes
        self._clock = clock
        self._recent: dict[tuple[str, str], float] = {}

    async def handle(self, device_id: str, utterance: Utterance) -> Display | None:
        """Returns what to show on the watch that spoke, or None for nothing."""
        if not utterance.final:
            return None
        text = " ".join(utterance.text.split())
        plain = _PUNCT.sub("", text).casefold()  # what was said, minus case and punctuation
        if len(_WORD.findall(text)) < MIN_WORDS and plain not in SINGLE_WORD_COMMANDS:
            log.info("dropped short utterance from %s: %r", device_id, text)
            return None
        agent_id = self._sessions.agent_id
        if agent_id is None:
            return NO_SESSION
        key = (device_id, plain)
        if self._is_repeat(key):
            log.info("dropped repeated utterance from %s: %r", device_id, text)
            return None
        text = self._fit(device_id, text)
        try:
            await self._agora.think(agent_id, text)
        except AgoraError as e:
            self._recent.pop(key, None)  # let the user say it again right away
            if e.agent_gone:
                log.warning("voice session %s is gone: %s", agent_id, e)
                self._sessions.stop()
                return NO_SESSION
            log.error("think failed for %s (status %s): %s", agent_id, e.status, e)
            return AGORA_FAILED
        return Display(title="You said", body=text)

    def _fit(self, device_id: str, text: str) -> str:
        data = text.encode("utf-8")
        if len(data) <= self._max_text_bytes:
            return text
        cut = data[: self._max_text_bytes].decode("utf-8", errors="ignore").rstrip()
        log.warning("truncated utterance from %s: %d -> %d bytes",
                    device_id, len(data), len(cut.encode("utf-8")))
        return cut

    def _is_repeat(self, key: tuple[str, str]) -> bool:
        """True if this device said the same thing within the window; otherwise
        remembers it. The key ignores case and punctuation."""
        now = self._clock()
        self._recent = {k: t for k, t in self._recent.items() if now - t < DEDUP_WINDOW_S}
        if key in self._recent:
            return True
        self._recent[key] = now
        return False


class AnswerRelay:
    """Turns what the voice assistant said into a display for the watch: each
    turn once, when it is final. The voice page re-sends turns it already sent
    (Agora hands it the whole conversation on every update)."""

    def __init__(self) -> None:
        self._shown_turns: deque[int] = deque(maxlen=64)

    def handle(self, transcript: AgentTranscript) -> Display | None:
        text = " ".join(transcript.text.split())
        if not transcript.final or not text:
            return None
        if transcript.turn_id is not None:
            if transcript.turn_id in self._shown_turns:
                return None
            self._shown_turns.append(transcript.turn_id)
        return Display(title="Assistant", body=text, vibrate=True)
