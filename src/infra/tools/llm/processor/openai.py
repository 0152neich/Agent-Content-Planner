from __future__ import annotations

from functools import cached_property

from langchain_openai import ChatOpenAI
from shared.settings.models.llm import OpenAISettings

from ..base import BaseLLMInput
from ..base import BaseLLMOutput
from ..base import BaseLLMService


class OpenAILLMInput(BaseLLMInput):
    pass


class OpenAILLMOutput(BaseLLMOutput):
    pass


class OpenAILLMService(BaseLLMService):
    settings: OpenAISettings

    @cached_property
    def client(self):
        return ChatOpenAI(
            model=self.settings.model,
            api_key=self.settings.api_key,
            openai_api_base=self.settings.api_base,
            temperature=self.settings.temperature,
            request_timeout=self.settings.request_timeout,
        )

    def process(self, inputs: OpenAILLMInput) -> OpenAILLMOutput:
        output_text = self.client.invoke(inputs.input_text).content
        return OpenAILLMOutput(output_text=output_text)
