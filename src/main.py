"""
Demo: Show every stop_reason the handler covers.

Cases 1-4 call the live API. Cases 5-7 are simulated (no API call) because
pause_turn, refusal, and model_context_window_exceeded can't be triggered
reliably on demand.
"""

from types import SimpleNamespace

from .config import get_client, MODEL
from .tools import GET_WEATHER_TOOL
from .handler import handle_response


def demo_case(label: str, messages: list, **kwargs) -> str:
    """
    Run a single demo case and show the result.

    Args:
        label: Human-readable label for this case
        messages: Conversation to send
        **kwargs: Additional args to pass to create() (e.g., max_tokens, stop_sequences)
                  Special param: _trigger (for display only, not sent to API)

    Returns:
        The final response text
    """

    client = get_client()

    # Extract special parameters (not for API)
    trigger = kwargs.pop('_trigger', 'see below')

    # Default parameters
    api_params = {
        "model": MODEL,
        "max_tokens": 1024,
        "messages": messages
    }

    # Override with remaining kwargs (only valid API parameters)
    api_params.update(kwargs)

    print(f"\n{'='*60}")
    print(f"CASE: {label}")
    print(f"{'='*60}")
    print(f"stop_reason trigger: {trigger}")

    response = client.messages.create(**api_params)

    print(f"Response stop_reason: {response.stop_reason}")

    result = handle_response(
        client,
        messages.copy() if isinstance(messages, list) else [messages],
        response,
        tools=[GET_WEATHER_TOOL]
    )

    print(f"\nResult:")
    print(result)

    return result


def _text_block(text: str):
    return SimpleNamespace(type="text", text=text)


def _fake_response(stop_reason: str, text: str = "", **extra):
    """Build a response-shaped object with the fields handle_response reads."""
    content = [_text_block(text)] if text else []
    return SimpleNamespace(stop_reason=stop_reason, content=content, **extra)


class _StubClient:
    """
    Stands in for the API client in simulated cases. Returns a canned end_turn
    so a simulated pause_turn can continue without a real request.
    """

    class _Messages:
        def create(self, **kwargs):
            return _fake_response("end_turn", "(continued after the paused turn)")

    messages = _Messages()


def simulated_case(label: str, response, _trigger: str) -> str:
    """Run handle_response on a canned response. No API call (except a stub for pause_turn)."""

    print(f"\n{'='*60}")
    print(f"CASE: {label}  [SIMULATED – no API call]")
    print(f"{'='*60}")
    print(f"stop_reason trigger: {_trigger}")
    print(f"Response stop_reason: {response.stop_reason}")

    result = handle_response(
        _StubClient(),
        [{"role": "user", "content": "(simulated conversation)"}],
        response,
        tools=[GET_WEATHER_TOOL]
    )

    print(f"\nResult:")
    print(result)

    return result


def main():
    """Run all demo cases."""

    print("\n" + "="*60)
    print("UNDERSTANDING stop_reason IN CLAUDE'S MESSAGES API")
    print("="*60)

    # Case 1: end_turn (natural completion)
    demo_case(
        "1. end_turn – Natural completion",
        [{"role": "user", "content": "What is 2+2?"}],
        _trigger="Short, straightforward question → Claude finishes naturally"
    )

    # Case 2: max_tokens (truncation)
    demo_case(
        "2. max_tokens – Truncated response",
        [{"role": "user", "content": "Count from 1 to 50"}],
        max_tokens=20,
        _trigger="max_tokens=20 is too low for the full response"
    )

    # Case 3: stop_sequence (custom sequence)
    demo_case(
        "3. stop_sequence – Custom stop sequence",
        [{"role": "user", "content": "Count from 1 to 10"}],
        stop_sequences=["3"],
        _trigger="stop_sequences=['3'] stops at '3'"
    )

    # Case 4: tool_use (tool calling)
    demo_case(
        "4. tool_use – Tool calling",
        [{"role": "user", "content": "What's the weather in San Francisco?"}],
        tools=[GET_WEATHER_TOOL],
        _trigger="Tool is available, Claude uses it"
    )

    # Case 5: pause_turn (simulated) – partial response is sent back, model continues
    simulated_case(
        "5. pause_turn – Server tool paused a long turn",
        _fake_response("pause_turn", "Searching the web for the latest results..."),
        _trigger="A server-side tool paused the turn; resend the partial response as-is"
    )

    # Case 6: refusal (simulated) – don't retry, report stop_details
    simulated_case(
        "6. refusal – Declined for safety reasons",
        _fake_response(
            "refusal",
            stop_details=SimpleNamespace(
                type="refusal",
                category="general_harms",
                explanation="The request was classified as potentially harmful."
            )
        ),
        _trigger="A classifier intervened; the handler reports category and explanation"
    )

    # Case 7: model_context_window_exceeded (simulated) – trim history, don't retry as-is
    simulated_case(
        "7. model_context_window_exceeded – Conversation too long",
        _fake_response("model_context_window_exceeded", "Here is the start of my answer..."),
        _trigger="The conversation exceeded the context window (not the same as max_tokens)"
    )

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print("""
✓ end_turn: Response completed naturally                 [live]
✓ max_tokens: Response truncated (hit token limit)       [live]
✓ stop_sequence: Response stopped at custom sequence     [live]
✓ tool_use: Claude called a tool (we ran it and continued) [live]
✓ pause_turn: Partial response sent back, model continued [simulated]
✓ refusal: Declined; category and explanation reported    [simulated]
✓ model_context_window_exceeded: Trim history, don't retry [simulated]

Key takeaway: Always check stop_reason and handle each case appropriately!
    """)


if __name__ == "__main__":
    main()
