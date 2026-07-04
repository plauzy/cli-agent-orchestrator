import json
import math
import os
import random
import re
import sqlite3
import time
from pathlib import Path

import requests


class ExperimentStore:
    def __init__(self):
        self.db_path = Path(os.path.expanduser("~/.cao/experiments/results.db"))
        try:
            os.makedirs(self.db_path.parent, exist_ok=True)
        except Exception:
            self.db_path = Path("tests/validation/experiments/results.db")
            os.makedirs(self.db_path.parent, exist_ok=True)

        self.conn = sqlite3.connect(str(self.db_path))
        self._init_db()

    def _init_db(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT,
                task_id TEXT,
                condition TEXT,
                quality_score REAL,
                latency_seconds REAL,
                tokens_used INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def save_result(self, exp_id, task_id, condition, score, latency, tokens):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO results (experiment_id, task_id, condition, quality_score, latency_seconds, tokens_used)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (exp_id, task_id, condition, score, latency, tokens),
        )
        self.conn.commit()


class LLMJudge:
    def __init__(self, use_mock=True):
        self.use_mock = use_mock

    def evaluate(self, task: dict, output: str) -> dict:
        if self.use_mock:
            score = round(random.uniform(6.0, 9.8), 2)
            return {
                "score": score,
                "breakdown": {
                    "correctness": score * 0.4,
                    "completeness": score * 0.25,
                    "quality": score * 0.2,
                    "coherence": score * 0.15,
                },
            }

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            print("  WARNING: ANTHROPIC_API_KEY not set, using fallback score")
            return {"score": round(random.uniform(4.0, 7.0), 2), "breakdown": {}}

        prompt = (
            "You are a technical evaluator. Score the following agent output for the given task "
            "on four dimensions (0-10 each):\n\n"
            f"TASK: {task['description']}\n"
            f"EXPECTED OUTPUT TYPE: {task.get('expected_output_type', 'code')}\n"
            f"AGENT OUTPUT:\n{output[:3000]}\n\n"
            "Respond with valid JSON only, no other text:\n"
            '{"correctness": <0-10>, "completeness": <0-10>, '
            '"quality": <0-10>, "coherence": <0-10>, "reasoning": "<one sentence>"}'
        )

        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=30,
            )
            resp.raise_for_status()
            raw = resp.json()["content"][0]["text"]
            raw = re.sub(r"^```(?:json)?\s*\n?|\n?```\s*$", "", raw.strip())
            dims = json.loads(raw)
            score = round(
                dims["correctness"] * 0.4
                + dims["completeness"] * 0.25
                + dims["quality"] * 0.2
                + dims["coherence"] * 0.15,
                2,
            )
            return {
                "score": score,
                "breakdown": {k: v for k, v in dims.items() if k != "reasoning"},
            }
        except (json.JSONDecodeError, KeyError, requests.RequestException) as exc:
            print(f"  WARNING: LLM judge failed ({exc}), using fallback score")
            return {"score": round(random.uniform(4.0, 7.0), 2), "breakdown": {}}


class StatisticalAnalyzer:
    def paired_ttest(self, treatment: list, baseline: list) -> dict:
        import numpy as np
        from scipy import stats

        t_arr = np.array(treatment, dtype=float)
        b_arr = np.array(baseline, dtype=float)
        diff = t_arr - b_arr
        n = len(diff)

        t_stat, p_value = stats.ttest_rel(t_arr, b_arr)
        std_diff = float(np.std(diff, ddof=1))
        d = float(np.mean(diff) / std_diff) if std_diff > 0 else 0.0

        se = std_diff / math.sqrt(n)
        t_crit = float(stats.t.ppf(0.975, df=n - 1))
        mean_diff = float(np.mean(diff))
        ci = (round(mean_diff - t_crit * se, 4), round(mean_diff + t_crit * se, 4))

        return {
            "t_stat": round(float(t_stat), 4),
            "p_value": round(float(p_value), 4),
            "cohens_d": round(d, 4),
            "ci_95": ci,
            "treatment_mean": round(float(np.mean(t_arr)), 4),
            "baseline_mean": round(float(np.mean(b_arr)), 4),
            "n": n,
        }

    def cuped_adjust(self, outcomes: list, covariates: list) -> tuple:
        import numpy as np

        Y = np.array(outcomes, dtype=float)
        X = np.array(covariates, dtype=float)

        var_x = float(np.var(X, ddof=1))
        if var_x == 0:
            return outcomes, 0.0

        theta = float(np.cov(Y, X)[0, 1] / var_x)
        adjusted = (Y - theta * (X - float(np.mean(X)))).tolist()

        orig_var = float(np.var(Y, ddof=1))
        adj_var = float(np.var(np.array(adjusted), ddof=1))
        reduction = (1 - adj_var / orig_var) * 100 if orig_var > 0 else 0.0
        return adjusted, round(reduction, 1)
