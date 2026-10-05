# CLAUDE.md

Guidance for working in this repo. The user-facing guide is [README.md](README.md).

## Purpose
Demo of Claude's Messages API `stop_reason` field. It calls the API through either OpenRouter.ai or the Anthropic Console and branches on each stop reason. Every stop reason is handled in `src/handler.py`.

## Layout
```
.env.example          # template; real key goes in .env (git-ignored)
requirements.txt      # anthropic, python-dotenv, pytest
src/
├── config.py         # loads .env, picks provider, builds client, sets MODEL
├── tools.py          # get_weather tool schema + dummy implementation + run_tool()
├── handler.py        # handle_response(): branches on stop_reason
└── main.py           # demo: 7 cases. 1-4 live (end_turn, max_tokens, stop_sequence, tool_use); 5-7 simulated (pause_turn, refusal, model_context_window_exceeded)
tests/
└── test_handler.py   # offline tests with fake responses (no API calls)
```

## Commands
```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip3 install -r requirements.txt
python -m src.main      # live demo, needs a key in .env
pytest tests/           # offline, but needs a key set in .env (see gotchas)
```

## stop_reason handling (src/handler.py)
| Value | Behavior |
|---|---|
| `end_turn` | return text |
| `max_tokens` | return text prefixed `[TRUNCATED ...]` |
| `stop_sequence` | return text plus `[Stopped at sequence: ...]` |
| `tool_use` | run tool, append assistant + `tool_result`, call API again, recurse |
| `pause_turn` | append assistant content as-is (no user message), call API again, recurse. Capped at `MAX_PAUSE_CONTINUATIONS` (5) |
| `refusal` | no retry; report `stop_details.category` and `explanation`, or a generic message if `stop_details` is `None` |
| `model_context_window_exceeded` | no retry; tell the caller to trim or summarize. Distinct from `max_tokens` |
| anything else | return `[Stop reason: ...]` |

`handle_response(client, messages, response, tools=None, pause_count=0)` returns strings, not exceptions. Keep that style when adding branches.

## Configuration facts (src/config.py)
- `API_PROVIDER` must be exactly `openrouter` or `anthropic`. It is not a URL.
- Key lookup: `OPENROUTER_API_KEY` first, then `ANTHROPIC_API_KEY`.
- OpenRouter base URL is `https://openrouter.ai/api`. The SDK appends `/v1/messages`, so do not add `/v1`. The host is `openrouter.ai`, not `openrouter.io`.
- `MODEL` depends on provider: `anthropic/claude-sonnet-5` on OpenRouter, `claude-sonnet-5-5` on Anthropic.
- The module raises `ValueError` at import time if no key is set.

## Gotchas
- `main.py`'s `demo_case` takes a `_trigger` kwarg for display. It must be popped before `api_params` is built. Anything else left in kwargs goes straight to `messages.create()` and fails with `TypeError`.
- `handle_tool_use` and the `pause_turn` branch import `MODEL` lazily from `.config`, so tests that reach those branches need a key set in `.env`.
- Use `python3` / `pip3` on Mac/Linux. The venv is `.venv`.
- Never commit `.env`.

## Known issues
- On OpenRouter, `response.stop_sequence` is `None` even when a stop sequence fired, so the demo prints `[Stopped at sequence: None]`. Possible fix: fall back to the sequence we requested.
- `pause_turn`, `refusal` details, and `model_context_window_exceeded` are handled and unit-tested, but not confirmed live through OpenRouter.

## Learning resources
- [Anthropic Messages API reference](https://docs.anthropic.com/messages/reference/)
- [OpenRouter docs](https://openrouter.ai/docs)
- [OpenRouter API keys](https://openrouter.ai/keys)
