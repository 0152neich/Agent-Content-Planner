from __future__ import annotations

from functools import cached_property

from langchain_anthropic import ChatAnthropic

from shared.settings.models.llm import AnthropicSettings

from ..base import BaseLLMInput
from ..base import BaseLLMOutput
from ..base import BaseLLMService


class AnthropicLLMInput(BaseLLMInput):
    pass


class AnthropicLLMOutput(BaseLLMOutput):
    pass


class AnthropicLLMService(BaseLLMService):
    settings: AnthropicSettings

    @cached_property
    def client(self):
        return ChatAnthropic(
            model=self.settings.model,
            api_key=self.settings.api_key,
            temperature=self.settings.temperature,
            timeout=self.settings.request_timeout,
        )

    def process(self, inputs: AnthropicLLMInput) -> AnthropicLLMOutput:
        output_text = self.client.invoke(inputs.input_text).content
        return AnthropicLLMOutput(output_text=output_text)
