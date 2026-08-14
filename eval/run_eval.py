import argparse
import json
import os
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from eval.metrics import calculate_all_metrics, generate_report
from graph.workflow import run_research


def run_benchmark(
    limit: int = 0, difficulty: str = "all", benchmark_file: str = "benchmark_questions.json"
):
    questions_file = (
        benchmark_file
        if os.path.isabs(benchmark_file)
        else os.path.join(os.path.dirname(__file__), benchmark_file)
    )

    if not os.path.exists(questions_file):
        print(f"❌ Error: Benchmark file '{questions_file}' not found.")
        return

    with open(questions_file, "r", encoding="utf-8") as f:
        questions = json.load(f)

    if difficulty != "all":
        questions = [q for q in questions if q.get("difficulty") == difficulty]

    if limit > 0:
        questions = questions[:limit]

    print(
        f"🚀 Starting Benchmark Evaluation using '{os.path.basename(questions_file)}' "
        f"on {len(questions)} questions (Difficulty: {difficulty})...\n"
    )

    for i, item in enumerate(questions, 1):
        q_id = item["id"]
        q_text = item["question"]
        q_diff = item["difficulty"]

        print(f"[{i}/{len(questions)}] ({q_id} - {q_diff}) Researching: {q_text}")
        start_t = time.time()

        try:
            state = run_research(q_text)
            passed = state.get("passed", False)
            scores = state.get("critic_scores", {})
            avg_score = scores.get("average_score", 0.0)
            rev_count = state.get("revision_count", 0)
            elapsed = round(time.time() - start_t, 2)

            status_str = "PASS ✅" if passed else "WARN ⚠️"
            print(
                f"   -> Result: {status_str} | Score: {avg_score} | Revisions: {rev_count} | Latency: {elapsed}s\n"
            )
        except Exception as e:
            print(f"   -> Error running question {q_id}: {e}\n")

        # Sleep briefly between queries to manage rate limits
        time.sleep(1)

    print("=" * 60)
    print("📊 BENCHMARK COMPLETE - CALCULATING METRICS")
    print("=" * 60)

    metrics = calculate_all_metrics()
    report_md = generate_report(metrics)
    print(report_md)

    # Save benchmark report markdown
    report_path = os.path.join(os.path.dirname(__file__), "latest_benchmark_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"Report saved to: {report_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Multi-Agent Research Benchmark Evaluation")
    parser.add_argument(
        "--limit", type=int, default=0, help="Limit number of benchmark questions to run"
    )
    parser.add_argument(
        "--difficulty",
        type=str,
        default="all",
        choices=["all", "easy", "medium", "hard"],
        help="Filter questions by difficulty",
    )
    parser.add_argument(
        "--file",
        type=str,
        default="benchmark_questions.json",
        help="Benchmark questions JSON file name or path",
    )
    args = parser.parse_args()

    run_benchmark(
        limit=args.limit, difficulty=args.difficulty, benchmark_file=args.file
    )
