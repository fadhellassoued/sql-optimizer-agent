from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class QueryRequest(BaseModel):
    sql_query: str

class ToolOutput(BaseModel):
    tool_name: str
    result: Dict[str, Any]

class AnalysisResponse(BaseModel):
    original_query: str
    optimized_query: Optional[str] = None
    estimated_cost_usd: Optional[float] = None
    issues: List[str] = []
    explanation: Optional[str] = None
    recommendations: List[str] = []
    execution_time_ms: Optional[float] = None
    data: Optional[List[Dict[str, Any]]] = None