"""
Agent 管理请求 Schema
"""
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AgentModelConfig(BaseModel):
    """Agent 模型配置（全部可选；provider+model 都填才覆盖默认）"""

    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(4096, ge=1)


class AgentParameters(BaseModel):
    """Agent 运行参数"""

    max_tool_calls: int = Field(10, ge=1)
    timeout: int = Field(300, ge=1)
    retry_on_failure: bool = False


class AgentCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str = Field(min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    prompt_id: str
    model_config_agent: Optional[AgentModelConfig] = Field(default=None, alias="model_config")
    parameters: AgentParameters = Field(default_factory=AgentParameters)
    tags: List[str] = []
    is_chat: bool = False
    enabled: bool = True


class AgentUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    prompt_id: Optional[str] = None
    model_config_agent: Optional[AgentModelConfig] = Field(default=None, alias="model_config")
    parameters: Optional[AgentParameters] = None
    tags: Optional[List[str]] = None
    is_chat: Optional[bool] = None
    enabled: Optional[bool] = None
