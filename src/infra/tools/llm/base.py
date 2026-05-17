from __future__ import annotations

from shared.base import BaseModel
from shared.base import BaseService


class BaseLLMInput(BaseModel):
    input_text: str


class BaseLLMOutput(BaseModel):
    output_text: str


class BaseLLMService(BaseService):
    def process(self, inputs: BaseLLMInput) -> BaseLLMOutput:
        return BaseLLMOutput(output_text="")
