import argparse
import json
import os
import sys
import time

# Ensure UTF-8 stdout on Windows PowerShell
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from eval.metrics import calculate_chat_metrics, generate_chat_report
from graph.workflow import chat


def run_benchmark(limit: int = 0, benchmark_file: str = "benchmark_questions.json"):
    questions_file = (
        benchmark_file
        if os.path.isabs(benchmark_file)
        else os.path.join(os.path.dirname(__file__), benchmark_file)
    )

    if not os.path.exists(questions_file):
        print(f"❌ Error: Benchmark file '{questions_file}' not found.")
        return

    with open(questions_file, "r", encoding="utf-8") as f:
        scenarios = json.load(f)

    if limit > 0:
        scenarios = scenarios[:limit]

    print(
        f"🚀 Starting ERP Sales Chatbot Benchmark Evaluation on {len(scenarios)} scenarios...\n"
    )

    eval_results = []

    for i, item in enumerate(scenarios, 1):
        s_id = item["id"]
        msg = item["message"]
        exp_intent = item["expected_intent"]

        print(f"[{i}/{len(scenarios)}] ({s_id}) Testing: \"{msg}\" (Expected: {exp_intent})")
        start_t = time.time()

        try:
            state = chat(msg)
            det_intent = state.get("intent", "off_topic")
            response = state.get("response", "")
            elapsed_ms = int((time.time() - start_t) * 1000)

            intent_match = (det_intent == exp_intent)
            status_str = "PASS ✅" if intent_match else "FAIL ❌"

            print(
                f"   -> Result: {status_str} | Detected: {det_intent} | Latency: {elapsed_ms}ms\n"
            )

            eval_results.append(
                {
                    "id": s_id,
                    "message": msg,
                    "expected_intent": exp_intent,
                    "detected_intent": det_intent,
                    "intent_match": intent_match,
                    "passed": intent_match,
                    "response": response,
                    "latency_ms": elapsed_ms,
                }
            )

        except Exception as e:
            print(f"   -> Error running scenario {s_id}: {e}\n")
            eval_results.append(
                {
                    "id": s_id,
                    "message": msg,
                    "expected_intent": exp_intent,
                    "detected_intent": "error",
                    "intent_match": False,
                    "passed": False,
                    "response": f"Error: {e}",
                    "latency_ms": int((time.time() - start_t) * 1000),
                }
            )

        time.sleep(1)

    print("=" * 60)
    print("📊 BENCHMARK EVALUATION COMPLETE")
    print("=" * 60)

    metrics = calculate_chat_metrics(eval_results)
    report_md = generate_chat_report(metrics, eval_results)
    print(report_md)

    # Save benchmark report markdown
    report_path = os.path.join(os.path.dirname(__file__), "latest_benchmark_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run ERP Sales Chatbot Benchmark Evaluation")
    parser.add_argument(
        "--limit", type=int, default=0, help="Limit number of benchmark scenarios to run"
    )
    parser.add_argument(
        "--file",
        type=str,
        default="benchmark_questions.json",
        help="Benchmark scenarios JSON file name or path",
    )
    args = parser.parse_args()

    run_benchmark(limit=args.limit, benchmark_file=args.file)
