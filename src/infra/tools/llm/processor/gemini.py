from __future__ import annotations

from functools import cached_property

from langchain_google_genai import ChatGoogleGenerativeAI
from shared.settings.models.llm import GeminiSettings

from ..base import BaseLLMInput
from ..base import BaseLLMOutput
from ..base import BaseLLMService


class GeminiLLMInput(BaseLLMInput):
    pass


class GeminiLLMOutput(BaseLLMOutput):
    pass


class GeminiLLMService(BaseLLMService):
    settings: GeminiSettings

    @cached_property
    def client(self):
        return ChatGoogleGenerativeAI(
            model=self.settings.model,
            api_key=self.settings.api_key,
            temperature=self.settings.temperature,
            timeout=self.settings.request_timeout,
        )

    def process(self, inputs: GeminiLLMInput) -> GeminiLLMOutput:
        output_text = self.client.invoke(inputs.input_text).content
        return GeminiLLMOutput(output_text=output_text)
