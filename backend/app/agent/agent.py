from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from google.adk.models import GeminiModel
from app.tools import (
    parser_tool, metadata_tool, execution_plan_tool,
    optimizer_tool, explainer_tool, recommender_tool
)
from app.config import settings

# Wrap async functions as ADK tools
tools = [
    FunctionTool(func=parser_tool.detect_issues, name="detect_sql_issues"),
    FunctionTool(func=metadata_tool.get_table_metadata, name="get_table_metadata"),
    FunctionTool(func=execution_plan_tool.get_execution_plan, name="get_execution_plan"),
    FunctionTool(func=optimizer_tool.optimize_query, name="optimize_sql"),
    FunctionTool(func=explainer_tool.explain_query_plan, name="explain_query"),
    FunctionTool(func=recommender_tool.recommend_structures, name="recommend_structures"),
]

# System prompt for the agent
INSTRUCTION = """
You are an expert SQL Optimization Assistant specialized in PostgreSQL.
Your job is to help users improve their SQL query performance and reduce costs.

When a user provides a SQL query, follow this workflow:
1. Use `detect_sql_issues` to find syntax/performance problems.
2. Use `get_table_metadata` to understand the tables involved.
3. Use `get_execution_plan` to see how the database actually runs it.
4. Use `optimize_sql` to get a rewritten version.
5. Use `explain_query` to generate a human-readable explanation.
6. Use `recommend_structures` to suggest long-term improvements.

Always present your final answer as a structured JSON with keys: 
issues, optimized_sql, estimated_cost_usd, explanation, recommendations.
Be concise, actionable, and professional.
"""

# Initialize the Gemini model
model = GeminiModel(model_name="gemini-1.5-flash", api_key=settings.GEMINI_API_KEY)

# Create the Agent
optimizer_agent = LlmAgent(
    name="sql_optimizer",
    model=model,
    instruction=INSTRUCTION,
    tools=tools,
    description="AI agent for optimizing SQL queries on PostgreSQL."
)