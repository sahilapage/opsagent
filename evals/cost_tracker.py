from __future__ import annotations
import json
import os
import time
from datetime import datetime
import structlog

log = structlog.get_logger()

COST_FILE = "evals/cost_log.json"

# Groq free tier — track usage to avoid hitting limits
GROQ_LIMITS = {
    "llama-3.3-70b-versatile": {"rpm": 30, "tpm": 6000, "rpd": 14400},
    "llama-3.1-8b-instant": {"rpm": 30, "tpm": 6000, "rpd": 14400},
}


def load_cost_log() -> dict:
    if os.path.exists(COST_FILE):
        with open(COST_FILE) as f:
            return json.load(f)
    return {"total_requests": 0, "total_tokens": 0, "runs": []}


def save_cost_log(log_data: dict) -> None:
    with open(COST_FILE, "w") as f:
        json.dump(log_data, f, indent=2)


def track_run(model: str, input_tokens: int, output_tokens: int,
              task: str = "") -> None:
    log_data = load_cost_log()
    total_tokens = input_tokens + output_tokens
    run = {
        "timestamp": datetime.utcnow().isoformat(),
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "task": task[:100],
    }
    log_data["total_requests"] += 1
    log_data["total_tokens"] += total_tokens
    log_data["runs"].append(run)
    # Keep last 1000 runs
    log_data["runs"] = log_data["runs"][-1000:]
    save_cost_log(log_data)


def get_summary() -> dict:
    log_data = load_cost_log()
    return {
        "total_requests": log_data["total_requests"],
        "total_tokens": log_data["total_tokens"],
        "recent_runs": log_data["runs"][-10:],
    }


if __name__ == "__main__":
    summary = get_summary()
    print(f"Total requests: {summary['total_requests']}")
    print(f"Total tokens:   {summary['total_tokens']}")
