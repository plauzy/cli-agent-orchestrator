import argparse
import json
import os
import statistics
import time
from collections import defaultdict
from pathlib import Path

import requests

from tests.validation.cao_client import CAOClient
from tests.validation.harness import ExperimentStore, LLMJudge, StatisticalAnalyzer

REGISTERED_EXPERIMENTS = ["topology"]


def run_experiment(
    exp_id: str,
    is_mock: bool,
    max_tasks: int | None,
    provider: str = "claude_code",
    agent_profile: str = "developer",
):
    print(f"\nStarting experiment: {exp_id} (mock={is_mock})")
    store = ExperimentStore()
    judge = LLMJudge(use_mock=is_mock)
    client = None if is_mock else CAOClient()

    if client:
        client.health_check()

    tasks_file = Path(__file__).parent / "tasks.json"
    with open(tasks_file) as f:
        tasks = json.load(f)

    if max_tasks:
        tasks = tasks[:max_tasks]

    conditions = ["baseline", "treatment"]
    print(
        f"Loaded {len(tasks)} tasks, {len(conditions)} conditions = {len(tasks) * len(conditions)} runs"
    )

    for task in tasks:
        for condition in conditions:
            print(f"  {task['task_id']} [{condition}]...", end=" ", flush=True)
            start = time.time()
            try:
                if is_mock:
                    time.sleep(0.1)
                    output = f"mock output for: {task['description']}"
                    tokens = 200
                else:
                    orchestration_type = "send_message" if condition == "baseline" else "assign"
                    session_name = f"eval_{exp_id}_{task['task_id']}_{condition}"
                    terminal_id = client.create_terminal(session_name, provider, agent_profile)
                    client.dispatch_task(terminal_id, task["description"], orchestration_type)
                    output, _ = client.poll_completion(terminal_id)
                    client.cleanup(session_name)
                    tokens = len(output.split())

                latency = time.time() - start
                result = judge.evaluate(task, output)
                store.save_result(
                    exp_id, task["task_id"], condition, result["score"], latency, tokens
                )
                print(f"score={result['score']:.2f} latency={latency:.1f}s")
            except Exception as exc:
                latency = time.time() - start
                print(f"ERROR: {exc}")
                store.save_result(exp_id, task["task_id"], condition, 0.0, latency, 0)

    print(f"Experiment '{exp_id}' complete.")


def generate_report(exp_id: str):
    print(f"\n{'=' * 65}")
    print(f"REPORT: {exp_id}")
    print("=" * 65)

    store = ExperimentStore()
    cursor = store.conn.cursor()

    # Latest result per (task_id, condition) — avoids stale rows from prior runs
    cursor.execute(
        """
        SELECT task_id, condition, quality_score
        FROM results
        WHERE experiment_id=? AND id IN (
            SELECT MAX(id) FROM results WHERE experiment_id=? GROUP BY task_id, condition
        )
        ORDER BY task_id, condition
        """,
        (exp_id, exp_id),
    )
    rows = cursor.fetchall()
    if not rows:
        print(f"No results found for '{exp_id}'.")
        return

    by_condition: dict[str, list[float]] = defaultdict(list)
    task_scores: dict[str, dict[str, float]] = defaultdict(dict)
    for task_id, condition, score in rows:
        by_condition[condition].append(score)
        task_scores[task_id][condition] = score

    print(f"{'Condition':<15} | {'N':<5} | {'Mean Score':<11} | Std Dev")
    print("-" * 50)
    for cond, scores in sorted(by_condition.items()):
        mean = statistics.mean(scores)
        std = statistics.stdev(scores) if len(scores) > 1 else 0.0
        print(f"{cond:<15} | {len(scores):<5} | {mean:<11.3f} | {std:.3f}")

    if "baseline" in by_condition and "treatment" in by_condition:
        # Pair by task_id for properly matched comparison
        paired_tasks = sorted(
            tid
            for tid, conds in task_scores.items()
            if "baseline" in conds and "treatment" in conds
        )
        b = [task_scores[tid]["baseline"] for tid in paired_tasks]
        t = [task_scores[tid]["treatment"] for tid in paired_tasks]

        if len(paired_tasks) < 2:
            print(f"\nPaired t-test: insufficient data (n={len(paired_tasks)}, need ≥2)")
            print("=" * 65)
            return

        analyzer = StatisticalAnalyzer()
        stat = analyzer.paired_ttest(t, b)

        print(f"\nPaired t-test (n={stat['n']})")
        print(f"  t={stat['t_stat']}, p={stat['p_value']}, Cohen's d={stat['cohens_d']}")
        print(f"  95% CI for mean diff: {stat['ci_95']}")
        print(f"  treatment mean={stat['treatment_mean']}, baseline mean={stat['baseline_mean']}")

        # CUPED adjustment using estimated_tokens as covariate
        tasks_file = Path(__file__).parent / "tasks.json"
        with open(tasks_file) as f:
            task_map = {task["task_id"]: task for task in json.load(f)}

        cov = [float(task_map.get(tid, {}).get("estimated_tokens", 500)) for tid in paired_tasks]
        _, reduction = analyzer.cuped_adjust(t + b, cov + cov)
        print(f"  CUPED variance reduction: {reduction}%")

        p, d = stat["p_value"], abs(stat["cohens_d"])
        if p < 0.05 and d > 0.5:
            decision = "SHIP IT"
        elif p < 0.10 and d > 0.2:
            decision = "INVESTIGATE"
        else:
            decision = "ABORT / INSUFFICIENT SIGNAL"
        print(f"\n  Decision: {decision}")

    print("=" * 65)


def dry_run():
    print("Running pre-flight checks...")
    base_url = "http://localhost:9889"

    try:
        resp = requests.get(f"{base_url}/health", timeout=5)
        status = resp.json().get("status", "unknown")
        print(f"  [OK] CAO server: {status}")
    except Exception as exc:
        print(f"  [FAIL] CAO server: {exc}")
        return

    try:
        resp = requests.get(f"{base_url}/agents/profiles", timeout=5)
        profiles = resp.json()
        names = (
            [p.get("name", str(p)) for p in profiles]
            if isinstance(profiles, list)
            else list(profiles.keys())
        )
        has_developer = any("developer" in str(n).lower() for n in names)
        flag = "OK" if has_developer else "WARN"
        print(f"  [{flag}] Agent profiles ({len(names)}): {names[:5]}")
        if not has_developer:
            print("         'developer' not found — use --agent-profile to specify one")
    except Exception as exc:
        print(f"  [WARN] Agent profiles: {exc}")

    tasks_file = Path(__file__).parent / "tasks.json"
    with open(tasks_file) as f:
        tasks = json.load(f)
    domains: dict[str, int] = defaultdict(int)
    for t in tasks:
        domains[t["domain"]] += 1
    print(f"  [OK]  Tasks: {len(tasks)} total — {dict(domains)}")

    api_key_set = bool(os.environ.get("ANTHROPIC_API_KEY"))
    flag = "OK" if api_key_set else "WARN"
    print(
        f"  [{flag}] ANTHROPIC_API_KEY: {'set' if api_key_set else 'not set (real scoring will use fallback)'}"
    )

    print("Pre-flight complete.")


def main():
    parser = argparse.ArgumentParser(description="CAO Evaluation & A/B Testing")
    parser.add_argument("--dry-run", action="store_true", help="Check setup without running")
    parser.add_argument("--mock", action="store_true", help="Use mock LLM responses")
    parser.add_argument("--max-tasks", type=int, default=None, help="Limit tasks per experiment")
    parser.add_argument("--experiment", type=str, default="topology", help="Experiment ID")
    parser.add_argument(
        "--all", dest="run_all", action="store_true", help="Run all registered experiments"
    )
    parser.add_argument(
        "--report-only", type=str, metavar="EXP_ID", help="Print report for an existing experiment"
    )
    parser.add_argument(
        "--provider", type=str, default="claude_code", help="CAO provider (default: claude_code)"
    )
    parser.add_argument(
        "--agent-profile", type=str, default="developer", help="Agent profile (default: developer)"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.dry_run:
        dry_run()
        return

    if args.report_only:
        generate_report(args.report_only)
        return

    if args.run_all:
        for exp_id in REGISTERED_EXPERIMENTS:
            run_experiment(exp_id, args.mock, args.max_tasks, args.provider, args.agent_profile)
            generate_report(exp_id)
    else:
        run_experiment(
            args.experiment, args.mock, args.max_tasks, args.provider, args.agent_profile
        )
        generate_report(args.experiment)


if __name__ == "__main__":
    main()
