"""Provider-independent retrieval evaluation utilities."""

from dataclasses import dataclass
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    question: str
    relevant_document_ids: frozenset[str]
    relevant_chunk_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RetrievalMetrics:
    hit_rate_at_k: float
    precision_at_k: float
    recall_at_k: float
    mrr: float
    citation_correctness: float
    cases: int


def _relevant(item: dict[str, Any], case: EvaluationCase) -> bool:
    document_id = str(item.get("document_id", ""))
    chunk_id = str(item.get("chunk_id", ""))
    return document_id in case.relevant_document_ids or chunk_id in case.relevant_chunk_ids


def evaluate_cases(
    cases: Iterable[EvaluationCase],
    retrieve: Callable[[str, int], list[dict[str, Any]]],
    *,
    k: int = 5,
) -> RetrievalMetrics:
    """Calculate metrics from deterministic relevance labels and returned hits."""
    if k < 1:
        raise ValueError("k must be positive")
    cases = list(cases)
    if not cases:
        return RetrievalMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0)

    hits = precision = recall = reciprocal_rank = citation = 0.0
    for case in cases:
        results = retrieve(case.question, k)[:k]
        relevant_results = [item for item in results if _relevant(item, case)]
        first = next((index for index, item in enumerate(results, 1) if _relevant(item, case)), None)
        hits += bool(relevant_results)
        precision += len(relevant_results) / k
        recall += len({str(item.get("document_id")) for item in relevant_results}) / max(
            1, len(case.relevant_document_ids)
        )
        reciprocal_rank += 1 / first if first else 0
        cited = [
            item for item in results
            if item.get("citation") is not None
        ]
        citation += (
            sum(_relevant(item, case) for item in cited) / len(cited)
            if cited
            else 1.0 if not relevant_results else 0.0
        )
    count = len(cases)
    return RetrievalMetrics(
        hit_rate_at_k=hits / count,
        precision_at_k=precision / count,
        recall_at_k=recall / count,
        mrr=reciprocal_rank / count,
        citation_correctness=citation / count,
        cases=count,
    )
