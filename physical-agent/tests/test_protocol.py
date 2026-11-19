import pytest
from pydantic import ValidationError

from pagent import protocol as p


def test_utterance_frame_from_a_watch_parses_into_text_lang_final():
    frame = '{"v":"1.0","type":"utterance","id":"msg-1","ts":1.0,"payload":{"text":"wake laptop A","lang":"en","final":true}}'

    msg = p.parse_frame(frame)

    assert msg.type == "utterance"
    assert msg.body == p.Utterance(text="wake laptop A", lang="en", final=True)


def test_utterance_defaults_to_final_english():
    msg = p.parse_frame('{"type":"utterance","payload":{"text":"hello there"}}')

    assert msg.body == p.Utterance(text="hello there", lang="en", final=True)


def test_utterance_without_text_is_rejected_as_a_protocol_error():
    with pytest.raises(p.ProtocolError):
        p.parse_frame('{"type":"utterance","payload":{"lang":"en"}}')


def test_frame_that_is_not_json_is_rejected_as_a_protocol_error():
    with pytest.raises(p.ProtocolError):
        p.parse_frame("not json")


def test_display_for_the_watch_round_trips_through_a_frame():
    raw = p.build_frame(p.Display(title="You said", body="wake laptop A", vibrate=True))

    msg = p.parse_frame(raw)

    assert msg.type == "display"
    assert msg.body == p.Display(title="You said", body="wake laptop A", vibrate=True)


def test_agent_transcript_from_the_voice_page_carries_text_turn_and_final():
    msg = p.parse_frame('{"type":"agent_transcript","payload":{"text":"Laptop A is awake.","turn_id":7,"final":true}}')

    assert msg.body == p.AgentTranscript(text="Laptop A is awake.", turn_id=7, final=True)


def test_hello_carries_the_device_token_and_hello_ack_says_who_the_coordinator_thinks_you_are():
    hello = p.parse_frame(p.build_frame(p.Hello(token="watch-token")))
    ack = p.parse_frame(p.build_frame(p.HelloAck(device_id="watch-1", kind="watch")))

    assert (hello.type, hello.body) == ("hello", p.Hello(token="watch-token"))
    assert (ack.type, ack.body) == ("hello_ack", p.HelloAck(device_id="watch-1", kind="watch"))


@pytest.mark.parametrize("bad_hello", [
    '{"type":"hello","payload":{"tokne":"super-secret-token"}}',
    '{"type":"hello","payload":{"token":"super-secret-token"',
    '{"type":"hello","payload":{"token":["super-secret-token"]}}',
])
def test_a_rejected_frame_never_puts_what_was_sent_into_the_error_text(bad_hello):
    with pytest.raises(p.ProtocolError) as e:
        p.parse_frame(bad_hello)

    assert "super-secret-token" not in str(e.value)
