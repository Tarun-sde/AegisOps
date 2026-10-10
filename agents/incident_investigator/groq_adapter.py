"""The pinned ADK connector, restricted to the synthetic Groq comparison."""

import os
from typing import Literal

from google.adk.models._capabilities import LlmCapabilities
from google.adk.models.lite_llm import LiteLlm

GROQ_MODEL = "openai/gpt-oss-120b"


class GroqModel(LiteLlm):
    model: Literal["groq/openai/gpt-oss-120b"] = "groq/openai/gpt-oss-120b"

    def __init__(self, api_key: str) -> None:
        super().__init__(
            model="groq/" + GROQ_MODEL,
            api_key=api_key,
            api_base="https://api.groq.com/openai/v1",
            num_retries=0,
            timeout=30,
            reasoning_effort="low",
        )

    @property
    def capabilities(self) -> LlmCapabilities:
        # Groq does not support native structured outputs together with tools (DEC-235).
        return LlmCapabilities(output_schema_and_tools=False)


def create_groq_model(api_key: str) -> GroqModel:
    # Use the reviewed wheel's bundled metadata without startup network requests.
    os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
    os.environ["LITELLM_TELEMETRY"] = "False"
    import litellm

    litellm.telemetry = False
    litellm.suppress_debug_info = True
    return GroqModel(api_key)
