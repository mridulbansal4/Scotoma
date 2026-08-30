"""The red agent's system prompt and its tool schema.

The agent never ingests untrusted free text. Its inputs are SHAP values, a threshold and
recall numbers, all numeric and schema-validated. If any part of the detector state were
attacker-influenced prose, the loop would contain a prompt-injection channel into its own
red team.
"""

SYSTEM_PROMPT = """You are a red-team analyst for a defensive payment-fraud research lab.
You propose parameter settings for pre-built, sandboxed attack simulators so that a fraud
detector can be stress-tested and hardened. You never write attack code and you never
describe how to attack a real payment system.

You are given the detector's top SHAP features, its current decision threshold, and
per-vector recall from the last round. Propose parameter sets likely to be missed.

Call the propose_campaigns tool exactly once. Every params object must validate against
the JSON Schema supplied for its vector_id."""

TOOL_NAME: str = "propose_campaigns"


def tool_schema(schemas: dict[str, dict]) -> dict:
    return {
        "name": TOOL_NAME,
        "description": "Return campaign parameter sets for the sandboxed simulators.",
        "input_schema": {
            "type": "object",
            "properties": {
                "proposals": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "vector_id": {"type": "string", "enum": sorted(schemas.keys())},
                            "params": {"type": "object"},
                            "rationale": {"type": "string"},
                        },
                        "required": ["vector_id", "params", "rationale"],
                    },
                }
            },
            "required": ["proposals"],
        },
    }


def user_message(state, schemas: dict[str, dict], k: int) -> str:
    import json

    return json.dumps(
        {
            "threshold": round(state.threshold, 4),
            "top_shap_features": state.top_shap_features,
            "per_vector_recall": {k2: round(v, 4) for k2, v in state.per_vector_recall.items()},
            "survivors": state.survivors,
            "proposals_requested": k,
            "param_schemas": schemas,
        },
        sort_keys=True,
    )
