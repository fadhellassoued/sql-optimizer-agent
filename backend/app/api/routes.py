from fastapi import APIRouter, HTTPException
from app.models.schemas import QueryRequest, AnalysisResponse
from app.tools import (
    detect_issues,
    get_table_metadata,
    get_execution_plan,
    optimize_sql,
    explain_query,
    recommend_structures,
    estimate_query_cost
)
import time

router = APIRouter()

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_query(request: QueryRequest):
    start_time = time.time()
    sql = request.sql_query

    try:
        # 1. Détecter les problèmes
        issues_result = await detect_issues(sql)
        issues = issues_result["issues"]

        # 2. Essayer d'obtenir le plan d'exécution (uniquement si la requête est valide)
        plan = {}
        try:
            plan = await get_execution_plan(sql)
        except Exception:
            plan = {"error": "Impossible d'obtenir le plan d'exécution"}

        # 3. Optimisation
        opt_result = await optimize_sql(sql)
        optimized = opt_result.get("optimized_sql", sql)

        # 4. Explication (via Gemini)
        explanation = await explain_query(sql, plan, issues)

        # 5. Recommandations
        recommendations = await recommend_structures(sql)
        
        cost_estimation = await estimate_query_cost(sql, plan)
        elapsed = (time.time() - start_time) * 1000



        return AnalysisResponse(
            original_query=sql,
            optimized_query=optimized,
            estimated_cost_usd=cost_estimation["cost_usd"],
            issues=issues,
            explanation=explanation,
            recommendations=recommendations,
            execution_time_ms=round(elapsed, 2)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))