"""Bounded dialogue-only contract. No tools, actions, secrets, or memory writes."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConversationTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    player_text: str = Field(min_length=1, max_length=400)
    npc_text: str = Field(min_length=1, max_length=600)


class NPCRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    name: str = Field(min_length=1, max_length=50)
    personality: str = Field(min_length=1, max_length=300)
    goals: list[str] = Field(max_length=3)
    knowledge: list[str] = Field(max_length=5)
    relationship: str = Field(max_length=30)
    recent_conversation: list[ConversationTurn] = Field(max_length=1)
    message: str = Field(min_length=1, max_length=400)

    @model_validator(mode="after")
    def bound_context(self) -> "NPCRequest":
        if len(self.model_dump_json().encode("utf-8")) > 4096:
            raise ValueError("NPC context too large")
        return self


class NPCResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=600)
