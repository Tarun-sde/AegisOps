"""The pinned ADK connector, restricted to the synthetic Groq comparison."""

import os
from collections.abc import AsyncGenerator
from typing import Literal

from google.adk.models._capabilities import LlmCapabilities
from google.adk.models.lite_llm import LiteLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

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

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse]:
        # Groq rejects incoming 'reasoning_content' on assistant messages in multi-turn history.
        # Strip thought parts from past turns before dispatching over the wire.
        sanitized_contents = []
        for content in llm_request.contents or []:
            filtered_parts = [p for p in content.parts or [] if not p.thought]
            if filtered_parts:
                sanitized_contents.append(types.Content(role=content.role, parts=filtered_parts))
        sanitized_request = llm_request.model_copy(update={"contents": sanitized_contents})
        async for response in super().generate_content_async(sanitized_request, stream=stream):
            yield response


def create_groq_model(api_key: str) -> GroqModel:
    # Use the reviewed wheel's bundled metadata without startup network requests.
    os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
    os.environ["LITELLM_TELEMETRY"] = "False"
    import litellm

    litellm.telemetry = False
    litellm.suppress_debug_info = True
    return GroqModel(api_key)
