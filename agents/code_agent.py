from __future__ import annotations
import sys
import os
import io
import re
import json
import time
import base64
import subprocess
import tempfile
import structlog
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from rag.config import get_settings
from agents.state import AgentState

log = structlog.get_logger()

MAX_RETRIES = 3
TIMEOUT_SECONDS = 30
CHARTS_DIR = "/tmp/opsagent_charts"
os.makedirs(CHARTS_DIR, exist_ok=True)


def get_llm():
    s = get_settings()
    return ChatGroq(model=s.groq_model_large, api_key=s.groq_api_key, temperature=0)


def clean_code(code: str) -> str:
    code = code.strip()
    if "```python" in code:
        code = code.split("```python")[1].split("```")[0].strip()
    elif "```" in code:
        code = code.split("```")[1].split("```")[0].strip()
    return code


# ── Code generation ────────────────────────────────────────────────────────────

CODE_GEN_PROMPT = """You are an expert Python programmer. Generate clean, executable Python code.

Rules:
- Write complete, runnable Python code with all imports
- Print results clearly
- Do NOT use input() or interactive functions
- Do NOT make network requests
- For charts: use matplotlib, save to /tmp/opsagent_charts/output.png, do NOT use plt.show()
- Available libraries: pandas, numpy, matplotlib, math, statistics, json, datetime, collections, itertools, functools, random, re, string, scipy (if needed)
- Handle edge cases gracefully

Return ONLY the Python code, no explanation, no markdown."""


def generate_code(task: str, context: str = "") -> str:
    llm = get_llm()
    prompt = f"Task: {task}"
    if context:
        prompt += f"\n\nContext/Data:\n{context}"
    response = llm.invoke([
        SystemMessage(content=CODE_GEN_PROMPT),
        HumanMessage(content=prompt),
    ])
    return clean_code(response.content)


def fix_code(task: str, code: str, error: str) -> str:
    llm = get_llm()
    prompt = f"""Fix this Python code that produced an error.

TASK: {task}
CODE:
{code}

ERROR:
{error}

Write the COMPLETE fixed Python code. Return ONLY code."""
    response = llm.invoke([HumanMessage(content=prompt)])
    return clean_code(response.content)


# ── Execution ──────────────────────────────────────────────────────────────────

def execute_code(code: str) -> tuple[bool, str, str | None]:
    """Execute code. Returns (success, output, chart_path_if_any)."""
    chart_path = None

    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.py', delete=False, dir='/tmp'
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )

        # Check if chart was generated
        expected_chart = f"{CHARTS_DIR}/output.png"
        if os.path.exists(expected_chart):
            chart_path = expected_chart

        if result.returncode == 0:
            output = result.stdout.strip()
            return True, output or "Code executed successfully (no output)", chart_path
        else:
            return False, result.stderr.strip(), None
    except subprocess.TimeoutExpired:
        return False, f"Timed out after {TIMEOUT_SECONDS}s", None
    except Exception as e:
        return False, str(e), None
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def run_with_retry(task: str, context: str = "") -> dict:
    code = generate_code(task, context)
    log.info("code_generated", lines=len(code.splitlines()))

    for attempt in range(1, MAX_RETRIES + 1):
        success, output, chart_path = execute_code(code)

        if success:
            log.info("code_success", attempt=attempt)

            # Check if output looks wrong — ask LLM to verify
            if output and len(output) > 10:
                verify = verify_output(task, output)
                if not verify["looks_correct"] and attempt < MAX_RETRIES:
                    log.info("output_looks_wrong", reason=verify["reason"])
                    code = refine_code(task, code, output, verify["reason"])
                    continue

            # Encode chart if generated
            chart_b64 = None
            if chart_path:
                with open(chart_path, "rb") as f:
                    chart_b64 = base64.b64encode(f.read()).decode("utf-8")
                os.unlink(chart_path)

            return {
                "success": True,
                "code": code,
                "output": output,
                "attempts": attempt,
                "chart_b64": chart_b64,
            }
        else:
            log.warning("code_failed", attempt=attempt, error=output[:100])
            if attempt < MAX_RETRIES:
                code = fix_code(task, code, output)

    return {
        "success": False,
        "code": code,
        "output": output,
        "attempts": MAX_RETRIES,
        "chart_b64": None,
    }


def verify_output(task: str, output: str) -> dict:
    """Ask LLM if the output looks correct for the task."""
    llm = get_llm()
    try:
        response = llm.invoke([HumanMessage(content=f"""Does this output look correct for the task?

TASK: {task}
OUTPUT: {output[:500]}

Reply with JSON only: {{"looks_correct": true/false, "reason": "brief reason"}}""")])
        raw = response.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        return json.loads(raw)
    except Exception:
        return {"looks_correct": True, "reason": "Could not verify"}


def refine_code(task: str, code: str, output: str, reason: str) -> str:
    """Improve code when output looks wrong."""
    llm = get_llm()
    response = llm.invoke([HumanMessage(content=f"""Improve this Python code. The output looks incorrect.

TASK: {task}
CODE: {code}
CURRENT OUTPUT: {output[:300]}
ISSUE: {reason}

Write improved Python code. Return ONLY code.""")])
    return clean_code(response.content)


# ── Specialized capabilities ───────────────────────────────────────────────────

def analyze_csv_data(csv_content: str, task: str) -> dict:
    """Analyze CSV data with actual code execution."""
    context = f"CSV Data (first 2000 chars):\n{csv_content[:2000]}"
    full_task = f"""Analyze this CSV data and {task}

Load the data using:
import pandas as pd
import io
csv_data = '''{csv_content[:3000]}'''
df = pd.read_csv(io.StringIO(csv_data))

Then perform the analysis and print results."""
    return run_with_retry(full_task)


def generate_unit_tests(code_to_test: str, function_name: str = "") -> dict:
    """Generate and run unit tests for given code."""
    task = f"""Write comprehensive unit tests for this code using the unittest module.

CODE TO TEST:
{code_to_test}

{"Focus on function: " + function_name if function_name else "Test all functions."}

Requirements:
- Use unittest.TestCase
- Test normal cases, edge cases, and error cases
- Run the tests at the end with unittest.main(verbosity=2)
- Include the original code in the test file"""
    return run_with_retry(task)


def explain_code(code: str) -> str:
    """Explain what code does line by line."""
    llm = get_llm()
    response = llm.invoke([
        SystemMessage(content="You are an expert Python teacher. Explain code clearly."),
        HumanMessage(content=f"""Explain this Python code in detail:

```python
{code}
```

Provide:
1. Overall purpose
2. Line-by-line explanation for key parts
3. Time and space complexity
4. Potential improvements"""),
    ])
    return response.content


def optimize_code(code: str) -> dict:
    """Profile and optimize code."""
    llm = get_llm()

    # Generate optimized version
    response = llm.invoke([HumanMessage(content=f"""Optimize this Python code for performance.

ORIGINAL CODE:
{code}

Provide:
1. The optimized code
2. What you changed and why
3. Expected performance improvement

Return the optimized code first, then explanation.""")])

    optimized = clean_code(response.content.split("\n\n")[0])

    # Run both and compare
    profiling_code = f"""
import time

# Original
original_code = {repr(code)}
optimized_code = {repr(optimized)}

exec_globals = {{}}

start = time.perf_counter()
exec(original_code, exec_globals)
original_time = time.perf_counter() - start

exec_globals2 = {{}}
start = time.perf_counter()
exec(optimized_code, exec_globals2)
optimized_time = time.perf_counter() - start

improvement = ((original_time - optimized_time) / original_time * 100) if original_time > 0 else 0
print(f"Original time: {{original_time:.4f}}s")
print(f"Optimized time: {{optimized_time:.4f}}s")
print(f"Improvement: {{improvement:.1f}}%")
"""
    success, output, _ = execute_code(profiling_code)
    return {
        "optimized_code": optimized,
        "profile_output": output if success else "Could not profile",
        "explanation": response.content,
    }


def detect_dependencies(code: str) -> list[str]:
    """Detect what pip packages the code needs."""
    imports = re.findall(r'^(?:import|from)\s+(\w+)', code, re.MULTILINE)
    stdlib = {
        'os', 'sys', 'io', 're', 'json', 'math', 'time', 'datetime',
        'collections', 'itertools', 'functools', 'random', 'string',
        'pathlib', 'typing', 'abc', 'copy', 'uuid', 'hashlib', 'base64',
        'subprocess', 'threading', 'multiprocessing', 'logging', 'unittest',
        'dataclasses', 'enum', 'contextlib', 'warnings', 'traceback'
    }
    external = [imp for imp in set(imports) if imp not in stdlib]
    return external


def format_output_as_table(data: list[dict]) -> str:
    """Format list of dicts as ASCII table."""
    if not data:
        return "No data"
    headers = list(data[0].keys())
    col_widths = {h: max(len(h), max(len(str(row.get(h, ''))) for row in data))
                  for h in headers}
    separator = "+" + "+".join("-" * (w + 2) for w in col_widths.values()) + "+"
    header_row = "|" + "|".join(f" {h:<{col_widths[h]}} " for h in headers) + "|"
    rows = [separator, header_row, separator]
    for row in data:
        rows.append("|" + "|".join(f" {str(row.get(h, '')):<{col_widths[h]}} "
                                    for h in headers) + "|")
    rows.append(separator)
    return "\n".join(rows)


# ── Parse intent ───────────────────────────────────────────────────────────────

CODE_INTENT_PROMPT = """Extract the code task intent. Return JSON only:
{
  "action": one of "run_code", "analyze_csv", "generate_tests",
             "explain_code", "optimize_code", "plot_chart",
  "task": "the specific coding task",
  "code": "existing code if user provided it or null",
  "data": "CSV or data content if provided or null"
}
Return ONLY valid JSON."""


def parse_code_intent(task: str) -> dict:
    s = get_settings()
    llm = ChatGroq(model=s.groq_model_fast, api_key=s.groq_api_key, temperature=0)
    response = llm.invoke([
        SystemMessage(content=CODE_INTENT_PROMPT),
        HumanMessage(content=task),
    ])
    try:
        raw = response.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        return json.loads(raw)
    except Exception:
        return {"action": "run_code", "task": task, "code": None, "data": None}


# ── Code node ──────────────────────────────────────────────────────────────────

def code_node(state: AgentState) -> AgentState:
    try:
        task = state["task"]
        intent = parse_code_intent(task)
        action = intent.get("action", "run_code")
        log.info("code_node", action=action)

        if action == "explain_code" and intent.get("code"):
            result_text = explain_code(intent["code"])
            return {
                **state,
                "results": state["results"] + [{"agent": "code", "output": result_text}],
                "final_answer": result_text,
            }

        elif action == "optimize_code" and intent.get("code"):
            opt_result = optimize_code(intent["code"])
            answer = f"**Optimized Code:**\n```python\n{opt_result['optimized_code']}\n```\n\n"
            answer += f"**Profile Results:**\n```\n{opt_result['profile_output']}\n```\n\n"
            answer += f"**Explanation:**\n{opt_result['explanation']}"
            return {
                **state,
                "results": state["results"] + [{"agent": "code", "output": answer}],
                "final_answer": answer,
            }

        elif action == "generate_tests" and intent.get("code"):
            test_result = generate_unit_tests(intent["code"])
            answer = format_code_result(test_result)
            return {
                **state,
                "results": state["results"] + [{"agent": "code", "output": answer}],
                "final_answer": answer,
            }

        elif action == "analyze_csv" and intent.get("data"):
            result = analyze_csv_data(intent["data"], intent.get("task", task))
            answer = format_code_result(result)
            return {
                **state,
                "results": state["results"] + [{"agent": "code", "output": answer}],
                "final_answer": answer,
            }

        else:
            # Default: run code for the task (includes plot_chart)
            result = run_with_retry(task)
            answer = format_code_result(result)

            # Detect dependencies for user info
            deps = detect_dependencies(result["code"])
            if deps:
                answer += f"\n\n_(Dependencies used: {', '.join(deps)})_"

            return {
                **state,
                "results": state["results"] + [{
                    "agent": "code",
                    "output": answer,
                    "chart_b64": result.get("chart_b64"),
                }],
                "final_answer": answer,
            }

    except Exception as e:
        log.error("code_node_error", error=str(e))
        return {**state, "error": str(e), "final_answer": f"Code agent error: {str(e)}"}


def format_code_result(result: dict) -> str:
    if result["success"]:
        answer = "✅ Code executed successfully!\n\n"
        answer += f"**Output:**\n```\n{result['output']}\n```\n\n"
        answer += f"**Code:**\n```python\n{result['code']}\n```"
        if result.get("chart_b64"):
            answer += "\n\n📊 Chart generated successfully."
        if result.get("attempts", 1) > 1:
            answer += f"\n\n_(Auto-fixed and retried {result['attempts']} times)_"
    else:
        answer = f"❌ Code execution failed after {result['attempts']} attempts.\n\n"
        answer += f"**Error:**\n```\n{result['output']}\n```\n\n"
        answer += f"**Last code:**\n```python\n{result['code']}\n```"
    return answer
