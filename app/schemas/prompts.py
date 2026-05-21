"""
提示词管理请求 Schema
"""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class PromptBlock(BaseModel):
    type: Literal["text", "messages_placeholder"]
    label: str = ""
    content: Optional[str] = None


class PromptCreate(BaseModel):
    code: str = Field(min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    prompt_type: Literal["chat", "workflow"] = "workflow"
    blocks: List[PromptBlock] = []
    bind_tools: List[str] = []
    tags: List[str] = []
    enabled: bool = True


class PromptUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    prompt_type: Optional[Literal["chat", "workflow"]] = None
    blocks: Optional[List[PromptBlock]] = None
    bind_tools: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    enabled: Optional[bool] = None
