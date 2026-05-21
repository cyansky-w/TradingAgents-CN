"""
提示词管理数据模型
"""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class PromptBlock(BaseModel):
    """提示词构建块"""
    type: Literal["text", "messages_placeholder"]
    label: str = ""
    content: Optional[str] = None  # 仅 text 类型需要


class PromptCreate(BaseModel):
    """创建提示词请求"""
    code: str = Field(min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    prompt_type: Literal["chat", "workflow"] = "workflow"
    blocks: List[PromptBlock] = []
    bind_tools: List[str] = []
    tags: List[str] = []
    enabled: bool = True


class PromptUpdate(BaseModel):
    """更新提示词请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    prompt_type: Optional[Literal["chat", "workflow"]] = None
    blocks: Optional[List[PromptBlock]] = None
    bind_tools: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    enabled: Optional[bool] = None
