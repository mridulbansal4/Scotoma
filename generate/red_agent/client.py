"""The Anthropic tool-use call, fence stripping, and a single repair retry."""

import json

from generate.red_agent.constraints import Proposal
from generate.red_agent.prompt import SYSTEM_PROMPT, TOOL_NAME, tool_schema, user_message
from runtime.config import load_config
from runtime.errors import RedAgentUnavailable

MAX_TOKENS: int = 4096
REPAIR_INSTRUCTION: str = (
    "Your previous reply was not valid JSON for the propose_campaigns tool. "
    "Return the tool call again with valid JSON and nothing else."
)
FENCE_MARKERS: tuple[str, ...] = ("```json", "```")


def strip_fences(text: str) -> str:
    cleaned = text.strip()
    for marker in FENCE_MARKERS:
        if cleaned.startswith(marker):
            cleaned = cleaned[len(marker) :]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def _parse(payload: object) -> list[Proposal]:
    if isinstance(payload, str):
        payload = json.loads(strip_fences(payload))
    if not isinstance(payload, dict) or "proposals" not in payload:
        raise ValueError("tool result carried no proposals array")
    return [
        Proposal(
            vector_id=str(item["vector_id"]),
            params=dict(item["params"]),
            rationale=str(item.get("rationale", "")),
        )
        for item in payload["proposals"]
    ]


def propose(state, schemas: dict[str, dict], k: int = 6) -> list[Proposal]:
    config = load_config()
    if not config.anthropic_api_key:
        raise RedAgentUnavailable("ANTHROPIC_API_KEY is empty; offline search will run instead")
    try:
        import anthropic
    except ImportError as exc:
        raise RedAgentUnavailable(f"anthropic sdk unavailable: {exc}") from exc

    client = anthropic.Anthropic(
        api_key=config.anthropic_api_key, timeout=config.red_agent_timeout_s
    )
    tool = tool_schema(schemas)
    messages = [{"role": "user", "content": user_message(state, schemas, k)}]

    for attempt in range(2):
        try:
            response = client.messages.create(
                model=config.red_agent_model,
                max_tokens=MAX_TOKENS,
                # Roughly six calls per round share this block, so it is worth caching.
                system=[
                    {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
                ],
                tools=[tool],
                tool_choice={"type": "tool", "name": TOOL_NAME},
                messages=messages,
            )
        except Exception as exc:  # noqa: BLE001 - the SDK raises a wide transport hierarchy
            raise RedAgentUnavailable(f"anthropic call failed: {exc}") from exc

        for block in response.content:
            if getattr(block, "type", None) == "tool_use":
                try:
                    return _parse(block.input)
                except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                    break
        if attempt == 0:
            messages.append({"role": "user", "content": REPAIR_INSTRUCTION})
    raise RedAgentUnavailable("malformed tool output survived one repair retry")
