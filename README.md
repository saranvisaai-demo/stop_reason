# Understanding stop_reason in Claude's Messages API

A small Python demo that shows what `stop_reason` means and how to branch on it. It works with **OpenRouter.ai** (recommended) or the **Anthropic Console**.

## What is `stop_reason`?

Every Messages API response has a `stop_reason` field that says **why** Claude stopped generating. Your code should branch on it. Otherwise a truncated answer looks complete, or a tool request gets ignored.

| `stop_reason` | Meaning | What your code does |
|---|---|---|
| `end_turn` | Claude finished naturally | Show the text |
| `max_tokens` | Hit your `max_tokens` (output limit) | Raise `max_tokens` or continue |
| `stop_sequence` | Emitted one of your `stop_sequences` | Handle the custom stop |
| `tool_use` | Claude wants a tool run | Run the tool, send `tool_result`, call again |
| `pause_turn` | Server-side tool paused a long turn | Send the partial response back as-is, call again |
| `refusal` | Declined for safety reasons | Don't retry as-is; show `stop_details` |
| `model_context_window_exceeded` | Conversation is longer than the context window | Trim or summarize older messages first |

### The four live cases in the demo

```python
if response.stop_reason == "end_turn":
    print(response.content[0].text)

elif response.stop_reason == "max_tokens":
    print("Response was truncated due to token limit")

elif response.stop_reason == "stop_sequence":
    print(f"Stopped at sequence: {response.stop_sequence}")

elif response.stop_reason == "tool_use":
    # Only case where you must call the API again
    tool_use = next(b for b in response.content if b.type == "tool_use")
    result = run_tool(tool_use.name, tool_use.input)
    messages.append({"role": "assistant", "content": response.content})
    messages.append({
        "role": "user",
        "content": [{
            "type": "tool_result",
            "tool_use_id": tool_use.id,
            "content": json.dumps(result),
        }],
    })
    response = client.messages.create(model=MODEL, max_tokens=1024, tools=tools, messages=messages)
```

### The other three

- **`pause_turn`**: Append `response.content` as an assistant message (no new user message) and call the API again. `src/handler.py` caps this at `MAX_PAUSE_CONTINUATIONS` (5) resends.
- **`refusal`**: Don't retry. Read `response.stop_details`, which has `category` and `explanation` and may be `None`.
- **`model_context_window_exceeded`**: This is not the same as `max_tokens`. Retrying as-is won't help. Trim or summarize the history first.

## Setup

### 1. Create a virtual environment and install dependencies

**Mac/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
```

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Add your API key

```bash
cp .env.example .env
```

Edit `.env` and uncomment **one** provider block:

**OpenRouter.ai (recommended)**
```bash
OPENROUTER_API_KEY=sk-or-v1-your-key-here
API_PROVIDER=openrouter
```
Get a key at https://openrouter.ai/keys

**Anthropic Console (direct)**
```bash
ANTHROPIC_API_KEY=sk-ant-your-key-here
API_PROVIDER=anthropic
```
Get a key at https://console.anthropic.com

Rules:
- `API_PROVIDER` must be exactly `openrouter` or `anthropic`. It is **not** a URL.
- Use only one provider. Keep the other commented out.
- `.env` is git-ignored. Never commit it.

### 3. Run the demo

```bash
python -m src.main
```

It runs seven cases and prints each `stop_reason`:
- **Cases 1-4 are live** (`end_turn`, `max_tokens`, `stop_sequence`, `tool_use`). They call the API.
- **Cases 5-7 are simulated** (`pause_turn`, `refusal`, `model_context_window_exceeded`). They feed a canned response into the real handler, so no API call is made. These can't be triggered on demand: `pause_turn` needs a server-side tool, and the other two depend on the context limit and the model's policy decisions.

### 4. Run the tests (optional)

```bash
pytest tests/
```

The tests use fake responses and make no API calls. The `pause_turn` path imports `src/config.py`, which needs a key to be set in `.env`, so have one there even though no request is sent.

## Provider settings

| | OpenRouter.ai | Anthropic Console |
|---|---|---|
| `.env` variables | `OPENROUTER_API_KEY`, `API_PROVIDER=openrouter` | `ANTHROPIC_API_KEY`, `API_PROVIDER=anthropic` |
| Base URL | `https://openrouter.ai/api` (set in `src/config.py`) | SDK default |
| Model ID | `anthropic/claude-sonnet-5` | `claude-sonnet-5-5` |
| Key format | `sk-or-v1-...` | `sk-ant-...` |

Model IDs differ by provider. `src/config.py` picks the right one from `API_PROVIDER`.

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `401 ... API key is invalid` | Placeholder key, or key from a different provider than `API_PROVIDER` | Paste a real key that matches the provider |
| `404 Not Found` on the first call | Wrong base URL or model ID for the provider | Base URL must be `openrouter.ai` (not `openrouter.io`), and the model ID must match the provider |
| `API key not found` | `.env` missing or not in the project root | Run `cp .env.example .env` in `stop_reason/` and add the key |
| `[Stopped at sequence: None]` | OpenRouter does not fill in `response.stop_sequence` | Known issue; the handler could fall back to the requested sequence |

## Agent loop pattern

```python
def agentic_loop(client, messages, tools):
    while True:
        response = client.messages.create(model=MODEL, max_tokens=1024, tools=tools, messages=messages)

        if response.stop_reason == "end_turn":
            return response.content[0].text

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_use = next(b for b in response.content if b.type == "tool_use")
            result = run_tool(tool_use.name, tool_use.input)
            messages.append({
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": tool_use.id, "content": json.dumps(result)}],
            })
            continue

        if response.stop_reason == "max_tokens":
            raise RuntimeError("Token limit hit: increase max_tokens")

        raise RuntimeError(f"Unhandled stop_reason: {response.stop_reason}")
```

## Learning resources

- [Anthropic Messages API reference](https://docs.anthropic.com/messages/reference/)
- [OpenRouter docs](https://openrouter.ai/docs)
- [OpenRouter API keys](https://openrouter.ai/keys)
