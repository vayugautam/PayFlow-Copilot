from app.services.rag_evaluation import EvaluationCase, evaluate_cases


def test_retrieval_metrics_and_citation_correctness_are_deterministic():
    cases = [
        EvaluationCase(
            "supported",
            "refund",
            frozenset({"refund-policy"}),
            frozenset({"refund-policy:0"}),
        ),
        EvaluationCase("unsupported", "weather", frozenset()),
    ]
    results = {
        "refund": [
            {
                "document_id": "refund-policy",
                "chunk_id": "refund-policy:0",
                "citation": {"document_id": "refund-policy", "chunk_index": 0},
            }
        ],
        "weather": [],
    }

    metrics = evaluate_cases(cases, lambda query, _: results[query], k=2)

    assert metrics.cases == 2
    assert metrics.hit_rate_at_k == 0.5
    assert metrics.precision_at_k == 0.25
    assert metrics.recall_at_k == 0.5
    assert metrics.mrr == 0.5
    assert metrics.citation_correctness == 1.0


def test_irrelevant_and_wrong_citation_are_not_counted_as_relevant():
    case = EvaluationCase("case", "refund", frozenset({"trusted"}))
    metrics = evaluate_cases(
        [case],
        lambda _, __: [
            {
                "document_id": "other-user",
                "citation": {"document_id": "other-user"},
            }
        ],
        k=1,
    )

    assert metrics.hit_rate_at_k == 0.0
    assert metrics.precision_at_k == 0.0
    assert metrics.recall_at_k == 0.0
    assert metrics.mrr == 0.0
    assert metrics.citation_correctness == 0.0


def test_empty_evaluation_is_safe():
    metrics = evaluate_cases([], lambda _, __: [], k=5)

    assert metrics.cases == 0
    assert metrics.hit_rate_at_k == 0.0
