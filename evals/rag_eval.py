from __future__ import annotations
import json
import time
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import structlog
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision
from langchain_groq import ChatGroq
from langchain_community.embeddings import HuggingFaceEmbeddings
from rag.chain import answer as rag_answer
from rag.config import get_settings
from langchain_groq import ChatGroq as GroqChat
from langchain_community.chat_models import ChatOpenAI
import httpx


log = structlog.get_logger()


def run_eval(test_cases_path: str = "evals/test_cases.json",
             output_path: str = "evals/results.json") -> dict:

    s = get_settings()

    # Load test cases
    with open(test_cases_path) as f:
        test_cases = json.load(f)[:10]

    log.info("eval_started", total=len(test_cases))

    questions = []
    answers = []
    contexts = []
    ground_truths = []
    latencies = []

    for i, tc in enumerate(test_cases):
        question = tc["question"]
        ground_truth = tc["ground_truth"]

        log.info("eval_question", num=i+1, total=len(test_cases),
                 question=question[:50])

        start = time.time()
        try:
            result = rag_answer(query=question)
            latency = time.time() - start

            questions.append(question)
            answers.append(result.answer)
            contexts.append([s.text for s in result.sources])
            ground_truths.append(ground_truth)
            latencies.append(latency)

        except Exception as e:
            log.error("eval_question_error", question=question[:50], error=str(e))
            questions.append(question)
            answers.append("Error")
            contexts.append([""])
            ground_truths.append(ground_truth)
            latencies.append(0)

    # Build RAGAS dataset
    dataset = Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths,
    })

    log.info("running_ragas_scoring")

    # Use Groq LLM for RAGAS
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper

    # groq_llm = LangchainLLMWrapper(
    #     ChatGroq(model=s.groq_model_large, api_key=s.groq_api_key, temperature=0)
    # )
    # groq_llm = LangchainLLMWrapper(
    #     GroqChat(model="llama-3.1-8b-instant", api_key=s.groq_api_key, temperature=0)
    # )
    groq_llm = LangchainLLMWrapper(
        GroqChat(
            model="llama-3.1-8b-instant",
            api_key=s.groq_api_key,
            temperature=0,
            request_timeout=120,  # 2 minute timeout per call
            max_retries=3,
        )
    )
    hf_embeddings = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")
    )

    # scores = evaluate(
    #     dataset=dataset,
    #     metrics=[faithfulness, answer_relevancy, context_precision],
    #     llm=groq_llm,
    #     embeddings=hf_embeddings,
    # )
    # Run metrics one at a time to avoid rate limits
    scores_dict = {}

    for metric_name, metric in [
        ("faithfulness", faithfulness),
        ("answer_relevancy", answer_relevancy),
        ("context_precision", context_precision),
    ]:
        try:
            time.sleep(15)  # wait between metrics
            result = evaluate(
                dataset=dataset,
                metrics=[metric],
                llm=groq_llm,
                embeddings=hf_embeddings,
                raise_exceptions=False,
                is_async=False, 
            )
            scores_dict[metric_name] = float(result[metric_name])
            log.info("metric_scored", metric=metric_name, score=scores_dict[metric_name])
            time.sleep(30)  # longer wait after each metric
        except Exception as e:
            log.error("metric_error", metric=metric_name, error=str(e))
            scores_dict[metric_name] = 0.0

    results = {
        "faithfulness": float(scores_dict["faithfulness"]),
        "answer_relevancy": float(scores_dict["answer_relevancy"]),
        "context_precision": float(scores_dict["context_precision"]),
        "avg_latency_s": sum(latencies) / len(latencies),
        "total_questions": len(test_cases),
        "thresholds": {
            "faithfulness": 0.85,
            "answer_relevancy": 0.80,
        },
        "passed": (
            float(scores_dict["faithfulness"]) >= 0.85 and
            float(scores_dict["answer_relevancy"]) >= 0.80
        ),
        "per_question": [
            {
                "question": q,
                "answer": a[:200],
                "latency_s": round(l, 2),
            }
            for q, a, l in zip(questions, answers, latencies)
        ]
    }

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    log.info("eval_complete",
             faithfulness=results["faithfulness"],
             answer_relevancy=results["answer_relevancy"],
             context_precision=results["context_precision"],
             passed=results["passed"])

    return results


if __name__ == "__main__":
    results = run_eval()
    print("\n" + "="*50)
    print("RAGAS EVAL RESULTS")
    print("="*50)
    print(f"Faithfulness:      {results['faithfulness']:.3f} (threshold: 0.85)")
    print(f"Answer Relevancy:  {results['answer_relevancy']:.3f} (threshold: 0.80)")
    print(f"Context Precision: {results['context_precision']:.3f}")
    print(f"Avg Latency:       {results['avg_latency_s']:.2f}s")
    print(f"Total Questions:   {results['total_questions']}")
    print(f"PASSED:            {results['passed']}")
    print("="*50)
