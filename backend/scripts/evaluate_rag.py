"""Run the RAG evaluation dataset against an injected retrieval adapter.

This script intentionally does not connect to production Qdrant. Integrations
must provide a retrieval callable and report their own measured scores.
"""

import json
from pathlib import Path

from app.services.rag_evaluation import EvaluationCase, evaluate_cases


def load_cases(path: Path) -> list[EvaluationCase]:
    return [EvaluationCase(**item) for item in json.loads(path.read_text(encoding="utf-8"))]


def evaluate_with_retriever(cases, retriever, k: int = 5):
    return evaluate_cases(cases, retriever, k=k)


if __name__ == "__main__":
    raise SystemExit(
        "Provide a retrieval adapter and call evaluate_with_retriever(); "
        "the script never targets a production collection automatically."
    )
