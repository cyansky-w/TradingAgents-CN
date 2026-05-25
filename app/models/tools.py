"""
工具管理数据模型
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """工具参数定义"""
    name: str
    type: str  # "string" | "integer" | "number" | "array" | "boolean"
    required: bool = True
    default: Optional[Any] = None
    description: Optional[str] = None


class ToolCreate(BaseModel):
    """创建工具请求"""
    code: str = Field(min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1)
    type: Literal["builtin", "rpc", "remote", "workflow"]
    handler: Optional[str] = None       # builtin 必填
    endpoint_url: Optional[str] = None  # rpc/remote 必填
    workflow_id: Optional[str] = None   # workflow 必填
    output_format: Optional[Literal["full", "summary"]] = None  # workflow 可选
    endpoint_method: Optional[Literal["GET", "POST", "PUT", "DELETE"]] = None
    headers: Optional[Dict[str, str]] = None
    auth_type: Optional[Literal["none", "api_key", "bearer", "basic"]] = None
    auth_config: Optional[Dict[str, str]] = None
    parameters: List[ToolParameter] = []
    output_schema: Optional[Dict[str, Any]] = None
    timeout: int = 300
    tags: List[str] = []
    enabled: bool = True
    health_check_url: Optional[str] = None


class ToolUpdate(BaseModel):
    """builtin 工具可编辑的字段（code 不可修改）"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    enabled: Optional[bool] = None
    timeout: Optional[int] = None


class ToolUpdateExtended(ToolUpdate):
    """rpc/remote/workflow 工具额外可编辑的字段"""
    parameters: Optional[List[ToolParameter]] = None
    output_schema: Optional[Dict[str, Any]] = None
    endpoint_url: Optional[str] = None
    endpoint_method: Optional[Literal["GET", "POST", "PUT", "DELETE"]] = None
    headers: Optional[Dict[str, str]] = None
    auth_type: Optional[Literal["none", "api_key", "bearer", "basic"]] = None
    auth_config: Optional[Dict[str, str]] = None
    health_check_url: Optional[str] = None
    workflow_id: Optional[str] = None
    output_format: Optional[Literal["full", "summary"]] = None
