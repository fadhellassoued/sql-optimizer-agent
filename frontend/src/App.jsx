import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

const API_URL = 'http://localhost:8000/api/v1/analyze';

function App() {
  const [sql, setSql] = useState('SELECT * FROM orders LIMIT 5');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const analyzeQuery = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await axios.post(API_URL, { sql_query: sql });
      setResult(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      <header>
        <h1> SQL Optimizer AI Agent</h1>
        <p>Analyse, optimise et explique vos requêtes SQL</p>
      </header>

      <main>
        <section className="input-section">
          <div className="editor-container">
            <label> Requête SQL</label>
            <textarea
              value={sql}
              onChange={(e) => setSql(e.target.value)}
              rows={6}
              className="sql-textarea"
            />
          </div>
          <button onClick={analyzeQuery} disabled={loading}>
            {loading ? '⏳ Analyse en cours...' : '🚀 Analyser'}
          </button>
        </section>

        {error && (
          <section className="error-section">
            <h3>❌ Erreur</h3>
            <pre>{error}</pre>
          </section>
        )}

        {result && (
          <section className="result-section">
            <ResultDisplay result={result} />
          </section>
        )}
      </main>
    </div>
  );
}

function ResultDisplay({ result }) {
  return (
    <div className="result-grid">
      <div className="card">
        <h3> Problèmes détectés</h3>
        {result.issues && result.issues.length > 0 ? (
          <ul>
            {result.issues.map((issue, i) => (
              <li key={i}>{issue}</li>
            ))}
          </ul>
        ) : (
          <p className="success">✅ Aucun problème détecté</p>
        )}
      </div>

      <div className="card">
        <h3> Requête optimisée</h3>
        <pre className="sql-code">{result.optimized_query || 'Aucune optimisation'}</pre>
      </div>

      <div className="card">
        <h3> Explication</h3>
        <p>{result.explanation}</p>
      </div>

      <div className="card">
        <h3> Métriques</h3>
        <ul>
          <li><strong>Coût estimé :</strong> {result.estimated_cost_usd !== undefined ? `$${result.estimated_cost_usd}` : 'N/A'}</li>
          <li><strong>Temps d'exécution :</strong> {result.execution_time_ms ? `${result.execution_time_ms} ms` : 'N/A'}</li>
        </ul>
      </div>

      <div className="card full-width">
        <h3> Recommandations</h3>
        {result.recommendations && result.recommendations.length > 0 ? (
          <ul>
            {result.recommendations.map((rec, i) => (
              <li key={i}>{rec}</li>
            ))}
          </ul>
        ) : (
          <p>Aucune recommandation supplémentaire</p>
        )}
      </div>
    </div>
  );
}

export default App;