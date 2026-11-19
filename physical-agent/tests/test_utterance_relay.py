"""话语转发：手表的话语 -> 当前语音会话的 /think -> 给手表的显示。

Seam: UtteranceRelay.handle()，外部边界（Agora、时钟）换成假的。
"""

import asyncio

from pagent.coordinator.agora import AgoraError, FakeAgora
from pagent.coordinator.relay import UtteranceRelay
from pagent.coordinator.voice import VoiceSessions
from pagent.protocol import Display, Utterance


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def make(agent_id: str | None = "agent-123", **kw):
    agora = FakeAgora()
    sessions = VoiceSessions()
    if agent_id:
        sessions.start(agent_id)
    clock = Clock()
    relay = UtteranceRelay(agora, sessions, clock=clock, **kw)
    return relay, agora, sessions, clock


def say(relay: UtteranceRelay, text: str, device: str = "watch-1", **kw) -> Display | None:
    return asyncio.run(relay.handle(device, Utterance(text=text, **kw)))


def test_utterance_is_injected_into_the_running_voice_session_and_echoed_to_the_watch():
    relay, agora, _, _ = make(agent_id="agent-123")

    shown = say(relay, "wake laptop A")

    assert agora.thoughts == [("agent-123", "wake laptop A")]
    assert shown == Display(title="You said", body="wake laptop A", vibrate=False)


def test_without_a_voice_session_the_watch_is_told_to_open_the_voice_page():
    relay, agora, _, _ = make(agent_id=None)

    shown = say(relay, "wake laptop A")

    assert agora.thoughts == []
    assert shown == Display(title="Open the voice page on your phone", body="", vibrate=True)


def test_blank_and_one_word_utterances_are_dropped_without_a_display():
    relay, agora, _, _ = make()

    shown = [say(relay, "   "), say(relay, "uh"), say(relay, " okay. ")]

    assert agora.thoughts == []
    assert shown == [None, None, None]


def test_same_utterance_within_three_seconds_is_forwarded_once():
    relay, agora, _, clock = make()

    first = say(relay, "Wake laptop A")
    clock.now += 2.9
    repeat = say(relay, "wake  laptop a.")

    assert agora.thoughts == [("agent-123", "Wake laptop A")]
    assert first is not None and repeat is None


def test_same_utterance_after_three_seconds_is_forwarded_again():
    relay, agora, _, clock = make()

    say(relay, "wake laptop A")
    clock.now += 3.1
    say(relay, "wake laptop A")

    assert len(agora.thoughts) == 2


def test_overlong_utterance_is_cut_to_the_byte_limit_on_a_whole_character_and_logged(caplog):
    relay, agora, _, _ = make(max_text_bytes=9)

    with caplog.at_level("WARNING"):
        shown = say(relay, "open café menu")  # é is two bytes; byte 9 is its first half

    assert agora.thoughts == [("agent-123", "open caf")]
    assert shown == Display(title="You said", body="open caf")
    assert "truncated" in caplog.text


def test_when_agora_fails_the_watch_is_told_and_the_same_words_can_be_retried_at_once():
    relay, agora, sessions, _ = make()
    agora.fail_next = AgoraError("upstream 503", status=503)

    failed = say(relay, "wake laptop A")
    retried = say(relay, "wake laptop A")

    assert failed == Display(title="Voice assistant error", body="Please say it again", vibrate=True)
    assert retried == Display(title="You said", body="wake laptop A")
    assert agora.thoughts == [("agent-123", "wake laptop A")]
    assert sessions.agent_id == "agent-123"


def test_when_agora_says_the_agent_is_gone_the_voice_session_ends():
    relay, agora, sessions, _ = make()
    agora.fail_next = AgoraError("agent not found", status=404, agent_gone=True)

    shown = say(relay, "wake laptop A")
    again = say(relay, "what is the status")

    assert shown == again == Display(title="Open the voice page on your phone", vibrate=True)
    assert sessions.agent_id is None
    assert agora.thoughts == []


def test_partial_utterances_wait_for_the_final_one():
    relay, agora, _, _ = make()

    partial = say(relay, "wake laptop", final=False)
    final = say(relay, "wake laptop A", final=True)

    assert partial is None and final is not None
    assert agora.thoughts == [("agent-123", "wake laptop A")]


def test_chinese_counts_each_character_as_a_word():
    relay, agora, _, _ = make()

    say(relay, "嗯", lang="zh")
    say(relay, "唤醒电脑A", lang="zh")

    assert agora.thoughts == [("agent-123", "唤醒电脑A")]


def test_confirm_yes_and_cancel_get_through_as_single_words():
    relay, agora, _, _ = make()

    for word in ["Confirm.", "yes", " CANCEL "]:
        say(relay, word)
    say(relay, "okay")

    assert [text for _, text in agora.thoughts] == ["Confirm.", "yes", "CANCEL"]
