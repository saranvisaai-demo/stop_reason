"""
Unit tests for the handler – tests stop_reason logic without API calls.
"""

import pytest
from unittest.mock import Mock
from anthropic import Anthropic

from src.handler import handle_response, MAX_PAUSE_CONTINUATIONS


class FakeContentBlock:
    """Fake content block for testing."""
    def __init__(self, text=None, **kwargs):
        self.text = text
        for k, v in kwargs.items():
            setattr(self, k, v)


class FakeMessage:
    """Fake Message response for testing."""
    def __init__(self, stop_reason: str, text: str = "", **kwargs):
        self.stop_reason = stop_reason
        self.content = [FakeContentBlock(text=text)] if text else []
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_end_turn():
    """Test end_turn: returns the text."""
    client = Mock(spec=Anthropic)
    messages = [{"role": "user", "content": "Hi"}]
    response = FakeMessage(stop_reason="end_turn", text="Hello!")

    result = handle_response(client, messages, response)
    assert result == "Hello!"


def test_max_tokens():
    """Test max_tokens: indicates truncation."""
    client = Mock(spec=Anthropic)
    messages = [{"role": "user", "content": "Hi"}]
    response = FakeMessage(stop_reason="max_tokens", text="Partial res")

    result = handle_response(client, messages, response)
    assert "TRUNCATED" in result
    assert "Partial res" in result


def test_stop_sequence():
    """Test stop_sequence: includes the matched sequence."""
    client = Mock(spec=Anthropic)
    messages = [{"role": "user", "content": "Hi"}]
    response = FakeMessage(
        stop_reason="stop_sequence",
        text="1, 2, 3",
        stop_sequence="3"
    )

    result = handle_response(client, messages, response)
    assert "1, 2, 3" in result
    assert "3" in result


def test_refusal():
    """Test refusal: indicates safety decline."""
    client = Mock(spec=Anthropic)
    messages = [{"role": "user", "content": "Bad request"}]
    response = FakeMessage(stop_reason="refusal")

    result = handle_response(client, messages, response)
    assert "REFUSAL" in result or "declined" in result


def test_empty_content():
    """Test handling of empty content."""
    client = Mock(spec=Anthropic)
    messages = [{"role": "user", "content": "Hi"}]
    response = FakeMessage(stop_reason="end_turn", text="")

    result = handle_response(client, messages, response)
    assert result == ""


def test_unknown_stop_reason():
    """Test unknown stop_reason."""
    client = Mock(spec=Anthropic)
    messages = [{"role": "user", "content": "Hi"}]
    response = FakeMessage(stop_reason="unknown_reason")

    result = handle_response(client, messages, response)
    assert "unknown_reason" in result


def test_pause_turn_resends_assistant_content_and_continues():
    """pause_turn: append the partial assistant turn (no new user message), call API again, return its result."""
    client = Mock(spec=Anthropic)
    client.messages.create.return_value = FakeMessage(stop_reason="end_turn", text="Done after pause")
    messages = [{"role": "user", "content": "Search for something"}]
    paused = FakeMessage(stop_reason="pause_turn", text="partial")

    result = handle_response(client, messages, paused, tools=[])

    assert result == "Done after pause"
    assert client.messages.create.call_count == 1
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["content"] is paused.content


def test_pause_turn_stops_after_continuation_cap():
    """pause_turn that never finishes -> give up after MAX_PAUSE_CONTINUATIONS resends."""
    client = Mock(spec=Anthropic)
    client.messages.create.side_effect = lambda **kwargs: FakeMessage(stop_reason="pause_turn", text="still going")
    messages = [{"role": "user", "content": "Search"}]

    result = handle_response(client, messages, FakeMessage(stop_reason="pause_turn", text="x"), tools=[])

    assert "PAUSED" in result
    assert client.messages.create.call_count == MAX_PAUSE_CONTINUATIONS


def test_refusal_includes_stop_details():
    """refusal with stop_details: report category and explanation, no API call."""
    client = Mock(spec=Anthropic)
    details = Mock(category="cyber", explanation="Possible malware request")
    messages = [{"role": "user", "content": "Write malware"}]
    response = FakeMessage(stop_reason="refusal", stop_details=details)

    result = handle_response(client, messages, response)

    assert "cyber" in result
    assert "Possible malware request" in result
    client.messages.create.assert_not_called()


def test_refusal_without_stop_details_uses_generic_message():
    """refusal with stop_details=None: generic message, no API call."""
    client = Mock(spec=Anthropic)
    messages = [{"role": "user", "content": "Hi"}]
    response = FakeMessage(stop_reason="refusal", stop_details=None)

    result = handle_response(client, messages, response)

    assert "declined" in result
    client.messages.create.assert_not_called()


def test_model_context_window_exceeded_does_not_retry():
    """model_context_window_exceeded: tell the caller to trim/summarize, never retry automatically."""
    client = Mock(spec=Anthropic)
    messages = [{"role": "user", "content": "Hi"}]
    response = FakeMessage(stop_reason="model_context_window_exceeded", text="partial")

    result = handle_response(client, messages, response)

    assert "CONTEXT WINDOW EXCEEDED" in result
    client.messages.create.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
