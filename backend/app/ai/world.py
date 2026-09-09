"""Bounded room prose; geography and identifiers never come from the provider."""

import re
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.domain.directions import OPPOSITE

def plain_text(value: str) -> str:
    if any(unicodedata.category(char).startswith("C") for char in value):
        raise ValueError("Control characters are not allowed")
    return value


def sentence_count(value: str) -> int:
    """Count punctuation runs, allowing closing quotes and a final unpunctuated sentence.

    Decimal dots and common title/Latin abbreviations are not sentence endings.
    This is a deterministic English prose convention, not linguistic inference.
    """
    value = re.sub(r"\b(?:Mr|Mrs|Ms|Dr|St|Prof|Sr|Jr)\.", "title", value, flags=re.I)
    value = re.sub(r"\b(?:e\.g\.|i\.e\.)", "example", value, flags=re.I)
    value = re.sub(r"(?<=\d)\.(?=\d)", "decimal", value)
    return len([part for part in re.split(r'''[.!?…。！？]+["'”’»]*''', value) if part.strip()])


class RoomProposalContent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=2000)

    @field_validator("name", "description")
    @classmethod
    def reject_controls(cls, value: str) -> str:
        return plain_text(value)

    @field_validator("description")
    @classmethod
    def bound_sentences(cls, value: str) -> str:
        if not 1 <= sentence_count(value) <= 5:
            raise ValueError("Descriptions require one to five sentences")
        return value


class WorldGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, str_strip_whitespace=True)
    brief: str = Field(min_length=1, max_length=400)
    source_name: str = Field(min_length=1, max_length=100)
    source_description: str = Field(min_length=1)
    direction: str
    return_direction: str

    @field_validator("brief")
    @classmethod
    def reject_controls(cls, value: str) -> str:
        return plain_text(value)

    @model_validator(mode="after")
    def bounds(self) -> "WorldGenerationRequest":
        if OPPOSITE.get(self.direction) != self.return_direction:
            raise ValueError("Invalid connection")
        if len(self.model_dump_json().encode("utf-8")) > 8192:
            raise ValueError("World context exceeds 8192 bytes")
        return self
