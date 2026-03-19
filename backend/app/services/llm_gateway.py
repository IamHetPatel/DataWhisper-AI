import json
import logging
import re
from typing import Any

import anthropic
from openai import OpenAI

from app.config import get_settings
from app.services.semantic_layer import resolve_user_term

_log = logging.getLogger(__name__)


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:  # noqa: BLE001
        pass

    fence_match = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.S | re.I)
    if fence_match:
        try:
            parsed = json.loads(fence_match.group(1))
            if isinstance(parsed, dict):
                return parsed
        except Exception:  # noqa: BLE001
            pass

    brace_match = re.search(r"\{.*\}", text, flags=re.S)
    if brace_match:
        try:
            parsed = json.loads(brace_match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except Exception:  # noqa: BLE001
            return None

    return None


_RESOLVE_SCHEMA_TERMS_TOOL = {
    "type": "function",
    "function": {
        "name": "resolve_schema_terms",
        "description": (
            "Resolve a human-readable measurement name (e.g. 'maximum force', 'tensile strength') "
            "to its exact UUID in the materials testing database. "
            "Call this for EVERY metric mentioned in the user's question before generating the final JSON output."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "term": {
                    "type": "string",
                    "description": "The human-readable measurement name to resolve (e.g. 'maximum force').",
                },
            },
            "required": ["term"],
        },
    },
}

_QUERY_PLANNER_SYSTEM_PROMPT = """You are the Query Planner for a MongoDB materials testing database.
Your sole purpose is to translate natural language questions into a precise JSON routing schema.

You are strictly forbidden from generating conversational text, explanations, or MongoDB queries.
You must output ONLY valid JSON matching the exact schema provided.

OPERATIONAL SEQUENCE:
1. Analyze the user's request to determine the primary intent.
2. Identify entities, metrics, and filtering conditions.
3. If the user mentions a specific metric (e.g., "maximum force", "tensile strength"), you MUST use the `resolve_schema_terms` tool to find its exact UUID before generating the final JSON. Do not guess UUIDs.
4. Construct the JSON payload.
5. Ensure the `ui_rendering_contract` accurately reflects the best visual representation.

DATABASE SCHEMA REFERENCE:
- Tests collection (_tests):
  - TestParametersFlat.CUSTOMER -> customer/company name (e.g. 'Company_1')
  - TestParametersFlat.MATERIAL -> material under test
  - TestParametersFlat.TESTER -> operator name (e.g. 'Tester_2')
  - TestParametersFlat.STANDARD -> test standard (e.g. 'DIN EN ISO 6892-1')
  - TestParametersFlat.TYPE_OF_TESTING_STR -> "tensile", "compression", or "flexure"
  - TestParametersFlat.MACHINE_TYPE_STR -> machine type string
  - name, state, testProgramId -> other test metadata
- Values collection (valuecolumns_migrated):
  - metadata.refId -> links to _tests._id
  - metadata.childId -> UUID-based measurement identifier
  - uploadDate -> ISODate, use for all time filtering (data range: 2026-02-27 to 2026-03-03)
  - values -> float array (measurement samples)

INTENT MAPPING:
- "show/list/find/fetch/which/what" -> query_intent: "lookup", operation: "raw_fetch"
- "how many/count/total number of" -> query_intent: "lookup", operation: "count"
- "compare/vs/difference/versus" -> query_intent: "comparison", operation: "welch_t_test"
- "trend/over time/drift/degradation/worsening/increase/decrease" -> query_intent: "trend_drift", operation: "linear_regression"
- "outlier/anomaly/abnormal/strange/suspicious" -> query_intent: "anomaly_check", operation: "iqr_outlier"
- "compliant/within limits/standard/ISO/within spec" -> query_intent: "validation_compliance", operation: "standard_deviation"
- "hypothesis/influence/effect of/impact" -> query_intent: "hypothesis", operation: "welch_t_test"
- "summary/overview/high level" -> query_intent: "summary", operation: "standard_deviation"

CONSTRAINTS:
- Use exact dotted field paths (e.g. TestParametersFlat.CUSTOMER, not just CUSTOMER).
- For metrics, always call resolve_schema_terms to get the UUID before outputting JSON.
- For grouping comparisons, set grouping_dimension to the relevant TestParametersFlat field.
- Map "comparison" intent to box_plot presentation, "trend" to line_chart, "anomaly" to scatter_plot.

OUTPUT SCHEMA (output this exact JSON structure, nothing else):
{
  "query_intent": "lookup|comparison|trend_drift|anomaly_check|validation_compliance|hypothesis|summary|clarification_needed",
  "data_resolution": {
    "target_collections": ["tests"|"values"],
    "filters": [{"field_path": string, "operator": "eq|in|gte|lte|regex", "value": any}],
    "metrics": [{"human_label": string, "resolved_uuid": string, "source_collection": "values"}]
  },
  "analytical_engine": {
    "operation": "raw_fetch|count|welch_t_test|iqr_outlier|linear_regression|standard_deviation",
    "grouping_dimension": string|null,
    "time_series_interval": "day|week|month"|null
  },
  "ui_rendering_contract": {
    "presentation_type": "data_table|box_plot|line_chart|scatter_plot|compliance_badge|text_only",
    "x_axis_mapping": string|null,
    "y_axis_mapping": string|null,
    "summary_text_directive": string
  }
}"""


_ANTHROPIC_RESOLVE_TOOL = {
    "name": "resolve_schema_terms",
    "description": (
        "Resolve a human-readable measurement name (e.g. 'maximum force', 'tensile strength') "
        "to its exact UUID in the materials testing database. "
        "Call this for EVERY metric mentioned in the user's question before generating the final JSON output."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "term": {
                "type": "string",
                "description": "The human-readable measurement name to resolve (e.g. 'maximum force').",
            },
        },
        "required": ["term"],
    },
}


class AnthropicGateway:
    def __init__(self) -> None:
        self.settings = get_settings()

    def is_ready(self) -> bool:
        return bool(self.settings.anthropic_api_key)

    def get_model(self, purpose: str) -> str:
        if purpose == "planner":
            return self.settings.anthropic_model_planner
        if purpose == "insight":
            return self.settings.anthropic_model_insight
        return self.settings.anthropic_model_query

    def generate_json(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1600,
        temperature: float = 0.0,
    ) -> dict[str, Any] | None:
        if not self.is_ready():
            return None
        try:
            client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt + "\n\nIMPORTANT: Output only valid JSON, no markdown.",
                messages=[{"role": "user", "content": user_prompt}],
            )
            content = response.content[0].text if response.content else ""
            if not content:
                return None
            return _extract_json_object(content)
        except Exception as exc:  # noqa: BLE001
            _log.warning("Anthropic generate_json failed: %s", exc)
            return None

    def generate_query_plan(
        self,
        question: str,
        model: str,
        max_tool_rounds: int = 5,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any] | None:
        """Call Claude with resolve_schema_terms tool use to produce QueryPlannerSchema JSON."""
        if not self.is_ready():
            return None
        try:
            client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)
            # Prepend conversation history so follow-up questions have context
            messages: list[dict[str, Any]] = []
            for turn in (history or []):
                if turn.get("role") in {"user", "assistant"}:
                    messages.append({"role": turn["role"], "content": turn["content"]})
            messages.append({
                "role": "user",
                "content": f"Translate this question into the JSON routing schema: {question}",
            })

            for _ in range(max_tool_rounds):
                response = client.messages.create(
                    model=model,
                    max_tokens=2000,
                    system=_QUERY_PLANNER_SYSTEM_PROMPT,
                    tools=[_ANTHROPIC_RESOLVE_TOOL],
                    messages=messages,
                )

                if response.stop_reason == "tool_use":
                    # Append assistant turn
                    messages.append({"role": "assistant", "content": response.content})
                    # Process tool calls and append results
                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use" and block.name == "resolve_schema_terms":
                            term = block.input.get("term", "")
                            try:
                                results = resolve_user_term(term, limit=5)
                            except Exception:  # noqa: BLE001
                                results = []
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(results),
                            })
                    messages.append({"role": "user", "content": tool_results})
                else:
                    # Extract text from final response
                    for block in response.content:
                        if hasattr(block, "text") and block.text:
                            return _extract_json_object(block.text)
                    return None

        except Exception as exc:  # noqa: BLE001
            _log.warning("Anthropic generate_query_plan failed: %s", exc)
            return None

        return None


class OpenAIGateway:
    def __init__(self) -> None:
        self.settings = get_settings()

    def is_ready(self) -> bool:
        return bool(self.settings.openai_api_key)

    def get_model(self, purpose: str) -> str:
        if purpose == "planner":
            return self.settings.openai_model_planner
        if purpose == "insight":
            return self.settings.openai_model_insight
        return self.settings.openai_model_query

    def generate_json(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1600,
        temperature: float = 0.0,
    ) -> dict[str, Any] | None:
        if not self.is_ready():
            return None

        try:
            client = OpenAI(api_key=self.settings.openai_api_key)
            response = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as exc:  # noqa: BLE001
            _log.warning("OpenAI generate_json failed: %s", exc)
            return None

        content = response.choices[0].message.content
        if not content:
            return None

        return _extract_json_object(content)

    def generate_query_plan(
        self,
        question: str,
        model: str,
        max_tool_rounds: int = 5,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any] | None:
        """Call OpenAI with the resolve_schema_terms tool to produce QueryPlannerSchema JSON.

        The LLM may call resolve_schema_terms multiple times to look up metric UUIDs
        before emitting the final JSON routing schema.
        """
        if not self.is_ready():
            return None

        try:
            client = OpenAI(api_key=self.settings.openai_api_key)
            # Prepend conversation history so follow-up questions have context
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": _QUERY_PLANNER_SYSTEM_PROMPT},
            ]
            for turn in (history or []):
                if turn.get("role") in {"user", "assistant"}:
                    messages.append({"role": turn["role"], "content": turn["content"]})
            messages.append({
                "role": "user",
                "content": f"Translate this question into the JSON routing schema: {question}",
            })

            for _ in range(max_tool_rounds):
                response = client.chat.completions.create(
                    model=model,
                    temperature=0.0,
                    tools=[_RESOLVE_SCHEMA_TERMS_TOOL],
                    tool_choice="auto",
                    messages=messages,
                )
                msg = response.choices[0].message
                finish_reason = response.choices[0].finish_reason

                if finish_reason == "tool_calls" and msg.tool_calls:
                    messages.append(msg)
                    for tc in msg.tool_calls:
                        if tc.function.name == "resolve_schema_terms":
                            try:
                                args = json.loads(tc.function.arguments)
                                term = args.get("term", "")
                                results = resolve_user_term(term, limit=5)
                            except Exception:  # noqa: BLE001
                                results = []
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": json.dumps(results),
                            })
                else:
                    content = msg.content or ""
                    return _extract_json_object(content)

        except Exception:  # noqa: BLE001
            return None

        return None


def get_gateway() -> AnthropicGateway | OpenAIGateway:
    """Return the active LLM gateway based on LLM_PROVIDER setting."""
    settings = get_settings()
    if settings.llm_provider.lower() == "anthropic":
        return AnthropicGateway()
    return OpenAIGateway()
