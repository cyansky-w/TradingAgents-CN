"""
工作流管理请求 Schema
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class NodePosition(BaseModel):
    x: float = 0
    y: float = 0


class WorkflowNodeConfig(BaseModel):
    """Agent 节点配置示例（子类按需扩展）"""
    pass


class WorkflowNode(BaseModel):
    id: str = Field(min_length=1, max_length=60)
    type: str = Field(pattern=r"^(agent|subflow|io)$")
    label: str = Field(default="", max_length=100)
    position: NodePosition = Field(default_factory=NodePosition)
    config: Dict[str, Any] = Field(default_factory=dict)


class WorkflowEdge(BaseModel):
    id: str = Field(min_length=1, max_length=60)
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)


class TriggerConfig(BaseModel):
    type: str = Field(default="manual", pattern=r"^(cron|event|manual)$")
    cron: Optional[str] = None
    event: Optional[str] = None


class WorkflowSettings(BaseModel):
    timeout: int = Field(default=3600, ge=1)
    on_failure: str = Field(default="notify", pattern=r"^(notify|stop|continue)$")
    retry_count: int = Field(default=0, ge=0)


class WorkflowCreate(BaseModel):
    code: str = Field(min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    version: int = Field(default=1, ge=1)
    trigger: TriggerConfig = Field(default_factory=TriggerConfig)
    message_template: str = Field(min_length=1, description="工作流用户消息模板")
    output_template: Optional[str] = None
    nodes: List[WorkflowNode] = Field(default_factory=list)
    edges: List[WorkflowEdge] = Field(default_factory=list)
    settings: WorkflowSettings = Field(default_factory=WorkflowSettings)
    tags: List[str] = Field(default_factory=list)
    enabled: bool = True


class WorkflowUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    version: Optional[int] = Field(default=None, ge=1)
    trigger: Optional[TriggerConfig] = None
    message_template: Optional[str] = None
    output_template: Optional[str] = None
    nodes: Optional[List[WorkflowNode]] = None
    edges: Optional[List[WorkflowEdge]] = None
    settings: Optional[WorkflowSettings] = None
    tags: Optional[List[str]] = None
    enabled: Optional[bool] = None
