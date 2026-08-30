"""The Gemini function-calling call, fence stripping, and a single repair retry."""

import json

from backend.generate.red_agent.constraints import Proposal
from backend.generate.red_agent.prompt import SYSTEM_PROMPT, TOOL_NAME, tool_schema, user_message
from backend.runtime.config import load_config
from backend.runtime.errors import RedAgentUnavailable

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
    if not config.gemini_api_key:
        raise RedAgentUnavailable("GEMINI_API_KEY is empty; offline search will run instead")
    try:
        from google import genai
        from google.genai import errors, types
    except ImportError as exc:
        raise RedAgentUnavailable(f"google-genai sdk unavailable: {exc}") from exc

    client = genai.Client(
        api_key=config.gemini_api_key,
        http_options=types.HttpOptions(timeout=int(config.red_agent_timeout_s * 1000)),
    )
    tool = types.Tool(function_declarations=[tool_schema(schemas)])
    # Gemini has no separate system role: the prompt rides in system_instruction, and the
    # repair turn is appended to contents the way the tool-use retry was.
    generation = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        max_output_tokens=MAX_TOKENS,
        tools=[tool],
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode=types.FunctionCallingConfigMode.ANY,
                allowed_function_names=[TOOL_NAME],
            )
        ),
    )
    contents = [user_message(state, schemas, k)]

    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model=config.red_agent_model,
                contents=contents,
                config=generation,
            )
        except (errors.APIError, OSError, ValueError) as exc:
            raise RedAgentUnavailable(f"gemini call failed: {exc}") from exc

        for call in response.function_calls or []:
            if call.name != TOOL_NAME:
                continue
            try:
                return _parse(dict(call.args or {}))
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                break
        if attempt == 0:
            contents.append(REPAIR_INSTRUCTION)
    raise RedAgentUnavailable("malformed tool output survived one repair retry")
