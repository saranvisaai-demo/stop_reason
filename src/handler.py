"""
Handler for Claude API responses – branches on stop_reason.
"""

import json
from typing import Any
from anthropic import Anthropic
from anthropic.types import Message

from .tools import run_tool

# Stop continuing a paused turn after this many resends, so a stuck server tool can't loop forever
MAX_PAUSE_CONTINUATIONS = 5


def handle_response(
    client: Anthropic,
    messages: list,
    response: Message,
    tools: list = None,
    pause_count: int = 0
) -> Any:
    """
    Handle a Claude API response based on stop_reason.

    Args:
        client: Anthropic client (needed for follow-up API calls)
        messages: Conversation history (modified in-place if tool_use or pause_turn)
        response: The API response
        tools: List of available tools (only needed for tool_use)
        pause_count: How many times this turn has already been resumed (pause_turn guard)

    Returns:
        The final response text if stop_reason is end_turn,
        or continues the loop if tool_use or pause_turn.
    """

    if response.stop_reason == "end_turn":
        # Natural completion – return the text
        if response.content and hasattr(response.content[0], 'text'):
            return response.content[0].text
        return ""

    elif response.stop_reason == "max_tokens":
        # Response was truncated
        text = ""
        if response.content and hasattr(response.content[0], 'text'):
            text = response.content[0].text
        return f"[TRUNCATED – max_tokens limit hit]\n{text}"

    elif response.stop_reason == "stop_sequence":
        # Custom stop sequence was matched
        text = ""
        stop_seq = getattr(response, 'stop_sequence', 'unknown')
        if response.content and hasattr(response.content[0], 'text'):
            text = response.content[0].text
        return f"{text}\n[Stopped at sequence: {stop_seq}]"

    elif response.stop_reason == "tool_use":
        # Claude wants to use a tool – handle it and continue
        return handle_tool_use(client, messages, response, tools)

    elif response.stop_reason == "pause_turn":
        # Server paused a long-running turn. Send the partial response back as-is
        # (no new user message) so the model can pick up where it left off.
        if pause_count >= MAX_PAUSE_CONTINUATIONS:
            return f"[PAUSED – gave up after {MAX_PAUSE_CONTINUATIONS} continuations]"

        messages.append({
            "role": "assistant",
            "content": response.content
        })

        from .config import MODEL

        next_response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            tools=tools,
            messages=messages
        )
        return handle_response(client, messages, next_response, tools, pause_count + 1)

    elif response.stop_reason == "refusal":
        # Safety refusal. Don't retry; report the category and explanation if the API gave them.
        details = getattr(response, "stop_details", None)
        if details is None:
            return "[REFUSAL] Claude declined this request for safety reasons."
        category = details.category or "unspecified"
        explanation = details.explanation or "no explanation provided"
        return f"[REFUSAL] category={category}: {explanation}"

    elif response.stop_reason == "model_context_window_exceeded":
        # The conversation is too long for the model's context window. Retrying as-is won't help.
        return (
            "[CONTEXT WINDOW EXCEEDED] The conversation is longer than the model can hold. "
            "Trim older messages or summarize them before sending again."
        )

    else:
        # Unknown stop reason
        return f"[Stop reason: {response.stop_reason}]"


def handle_tool_use(
    client: Anthropic,
    messages: list,
    response: Message,
    tools: list
) -> Any:
    """
    Handle tool_use stop reason: run the tool and continue the conversation.

    Args:
        client: Anthropic client
        messages: Conversation history (modified in-place)
        response: The API response with tool_use
        tools: List of available tools

    Returns:
        The final response text after the tool result
    """

    # Find the tool_use block in the response
    tool_use_block = None
    for content in response.content:
        if content.type == "tool_use":
            tool_use_block = content
            break

    if not tool_use_block:
        return "[ERROR] No tool_use block found in response"

    # Extract tool info
    tool_name = tool_use_block.name
    tool_input = tool_use_block.input
    tool_use_id = tool_use_block.id

    print(f"  → Claude is calling tool: {tool_name}")
    print(f"    Input: {json.dumps(tool_input)}")

    # Run the tool
    tool_result = run_tool(tool_name, tool_input)
    print(f"    Result: {tool_result}")

    # Add assistant's response (with tool_use) to messages
    messages.append({
        "role": "assistant",
        "content": response.content
    })

    # Add the tool result as a user message
    messages.append({
        "role": "user",
        "content": [{
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": tool_result
        }]
    })

    # Call the API again to continue the conversation
    # Claude will now have the tool result and can formulate a response
    from .config import MODEL

    next_response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        tools=tools,
        messages=messages
    )

    # Recursively handle the response (it might be end_turn, or tool_use again, etc.)
    return handle_response(client, messages, next_response, tools)
