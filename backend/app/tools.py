import sqlglot
from sqlglot import parse_one
from sqlalchemy import text
from app.core.database import AsyncSessionLocal
from app.config import settings
import json
import groq
from typing import List, Dict, Any

# Initialize Groq client
client = groq.Groq(api_key=settings.GROQ_API_KEY)

# ---------- OUTIL 1 : Parseur (corrigé) ----------
async def detect_issues(sql: str) -> dict:
    issues = []
    try:
        parsed = parse_one(sql, dialect="postgres")
        if parsed.find(sqlglot.expressions.Star):
            issues.append("SELECT * détecté – précisez les colonnes pour réduire le volume.")
        if not parsed.find(sqlglot.expressions.Where):
            issues.append("Clause WHERE manquante – cela scanne toute la table.")
        # Détection CROSS JOIN corrigée
        for node in parsed.find_all(sqlglot.expressions.Join):
            if node.args.get('kind', '').upper() == 'CROSS':
                issues.append("CROSS JOIN détecté – préférez un INNER JOIN avec condition.")
                break
        if not parsed.find(sqlglot.expressions.Limit):
            issues.append("LIMIT absent – pensez à limiter le nombre de résultats.")
    except Exception as e:
        issues.append(f"Erreur de parsing : {str(e)}")
    return {"issues": issues, "is_valid": len(issues) == 0}

# ---------- OUTIL 2 : Métadonnées  ----------
async def get_table_metadata(table_name: str) -> dict:
    async with AsyncSessionLocal() as session:
        query = """
            SELECT 
                c.reltuples::bigint AS row_count,
                pg_total_relation_size(c.oid) AS total_bytes
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' 
              AND c.relname = :table_name
              AND c.relkind = 'r'
        """
        result = await session.execute(text(query), {"table_name": table_name})
        row = result.fetchone()
        if not row:
            return {"error": f"Table '{table_name}' non trouvée dans le schéma public"}
        idx_query = """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public' AND tablename = :table_name
        """
        idx_result = await session.execute(text(idx_query), {"table_name": table_name})
        indexes = idx_result.fetchall()
        col_query = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :table_name
        """
        col_result = await session.execute(text(col_query), {"table_name": table_name})
        columns = [row[0] for row in col_result.fetchall()]
        return {
            "row_count": row.row_count if row.row_count is not None else 0,
            "size_bytes": row.total_bytes,
            "size_mb": round(row.total_bytes / (1024*1024), 2),
            "indexes": [{"name": i[0], "definition": i[1]} for i in indexes],
            "columns": columns
        }

# ---------- OUTIL 3 : Plan d'exécution ----------
async def get_execution_plan(sql: str) -> dict:
    async with AsyncSessionLocal() as session:
        explain_sql = f"EXPLAIN (ANALYZE, FORMAT JSON) {sql}"
        result = await session.execute(text(explain_sql))
        plan_json = result.fetchone()[0]
        plan = plan_json[0]["Plan"]
        return {
            "plan_type": plan.get("Node Type"),
            "total_cost": plan.get("Total Cost"),
            "actual_rows": plan.get("Actual Rows"),
            "actual_time_ms": plan.get("Actual Total Time"),
            "scanned_pages": plan.get("Shared Hit Blocks", 0) + plan.get("Shared Read Blocks", 0)
        }

# ---------- OUTIL 4 : Optimiseur  ----------
async def optimize_sql(sql: str) -> dict:
    try:
        parsed = parse_one(sql, dialect="postgres")
        modifications = []

        # 1. Remplacer SELECT * par les colonnes
        for select in parsed.find_all(sqlglot.expressions.Select):
            has_star = any(isinstance(expr, sqlglot.expressions.Star) for expr in select.args.get('expressions', []))
            if has_star:
                from_clause = select.args.get('from')
                if from_clause and from_clause.args.get('expressions'):
                    table = from_clause.args['expressions'][0]
                    table_name = table.args.get('this', table).name
                    meta = await get_table_metadata(table_name)
                    if 'error' not in meta:
                        columns = meta.get('columns', [])
                        if columns:
                            select.set('expressions', [sqlglot.expressions.Column(this=col) for col in columns[:5]])
                            modifications.append("SELECT * remplacé par les colonnes")
                        else:
                            modifications.append("Impossible de remplacer SELECT * (colonnes non disponibles)")

        # 2. Ajouter une clause WHERE correctement
        if not parsed.find(sqlglot.expressions.Where):
            date_columns = ['order_purchase_timestamp', 'created_at', 'updated_at', 'date']
            table_name = None
            for table in parsed.find_all(sqlglot.expressions.Table):
                table_name = table.name
                break
            if table_name:
                meta = await get_table_metadata(table_name)
                if 'error' not in meta:
                    existing_cols = meta.get('columns', [])
                    for col in date_columns:
                        if col in existing_cols:
                            condition = sqlglot.parse_one(f"{col} > NOW() - INTERVAL '30 days'", dialect="postgres")
                            # Créer un nœud Where correct
                            where_node = sqlglot.expressions.Where(this=condition)
                            parsed.set('where', where_node)
                            modifications.append(f"Ajout de WHERE {col} > NOW() - INTERVAL '30 days'")
                            break

        # 3. Ajouter LIMIT 1000 si absent
        if not parsed.find(sqlglot.expressions.Limit):
            parsed = parsed.limit(1000)
            modifications.append("Ajout de LIMIT 1000")

        optimized = parsed.sql(dialect="postgres")
        return {
            "optimized_sql": optimized,
            "rule_applied": ", ".join(modifications) if modifications else "Aucune optimisation nécessaire"
        }
    except Exception as e:
        return {"optimized_sql": sql, "error": str(e)}

# ---------- OUTIL 5 : Explicateur (via Groq) ----------
async def explain_query(sql: str, plan: dict, issues: list) -> str:
    prompt = f"""
    Vous êtes un expert en performance SQL. Expliquez en langage clair pourquoi cette requête est lente et comment l'améliorer.
    SQL : {sql}
    Plan d'exécution : {json.dumps(plan, indent=2)}
    Problèmes détectés : {issues}
    Réponse concise (max 100 mots) et actionable.
    """
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a SQL performance expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=200
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erreur Groq : {str(e)}"

# ---------- OUTIL 6 : Recommandation ----------
async def recommend_structures(sql: str) -> list:
    recommendations = []
    async with AsyncSessionLocal() as session:
        idx_check = """
            SELECT 1 FROM pg_indexes
            WHERE tablename = 'orders' AND indexdef LIKE '%order_purchase_timestamp%'
        """
        exists = await session.execute(text(idx_check))
        if not exists.fetchone():
            recommendations.append("Index sur orders(order_purchase_timestamp) à envisager si vous filtrez souvent par date.")
    return recommendations

# ---------- OUTIL 7 : Estimation du coût  ----------
async def estimate_query_cost(sql: str, plan: dict) -> dict:
    try:
        parsed = parse_one(sql, dialect="postgres")
        tables = []
        for table in parsed.find_all(sqlglot.expressions.Table):
            tables.append(table.name)

        if not tables:
            return {"cost_usd": 0.0, "bytes_scanned": 0, "details": "Aucune table trouvée"}

        total_bytes = 0
        async with AsyncSessionLocal() as session:
            for table_name in tables:
                query = "SELECT pg_total_relation_size(:table_name) AS size"
                result = await session.execute(text(query), {"table_name": table_name})
                row = result.fetchone()
                if row and row.size:
                    total_bytes += row.size

        scanned_pages = plan.get("scanned_pages", 0)
        if scanned_pages > 0:
            scanned_bytes = scanned_pages * 8192
        else:
            # Fallback : on prend toute la table (pire cas)
            scanned_bytes = total_bytes

        cost_usd = (scanned_bytes / 1e12) * 5.0  # Tarif BigQuery 5$/To

        return {
            "cost_usd": round(cost_usd, 6),
            "bytes_scanned": scanned_bytes,
            "bytes_scanned_mb": round(scanned_bytes / (1024*1024), 2),
            "total_table_bytes": total_bytes,
            "details": f"Estimé sur {scanned_bytes / (1024*1024):.2f} Mo"
        }
    except Exception as e:
        return {"cost_usd": 0.0, "bytes_scanned": 0, "details": f"Erreur : {str(e)}"}

async def execute_query(sql: str, limit: int = 100) -> List[Dict]:
    """
    Exécute une requête SQL et retourne les résultats sous forme de liste de dictionnaires.
    Ajoute automatiquement une clause LIMIT si elle est absente.
    """
    async with AsyncSessionLocal() as session:
        # Ajouter LIMIT si absent
        parsed = parse_one(sql, dialect="postgres")
        if not parsed.find(sqlglot.expressions.Limit):
            parsed = parsed.limit(limit)
        limited_sql = parsed.sql(dialect="postgres")
        
        result = await session.execute(text(limited_sql))
        rows = result.fetchall()
        columns = result.keys()
        data = [dict(zip(columns, row)) for row in rows]
        return data