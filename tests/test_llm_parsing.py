import pytest

from app.llm import prompts
from app.llm.base import ClassifyItem
from app.llm.stub import StubLLMClient


def test_parse_classify_plain_json():
    text = '{"results": [{"index": 0, "category": "Food"}, {"index": 1, "category": "Shopping"}]}'
    mapping = prompts.parse_classify_response(text, {0, 1})
    assert mapping == {0: "Food", 1: "Shopping"}


def test_parse_classify_with_code_fence():
    text = '```json\n{"results": [{"index": 2, "category": "Travel"}]}\n```'
    mapping = prompts.parse_classify_response(text, {2})
    assert mapping == {2: "Travel"}


def test_parse_classify_drops_unknown_category_and_index():
    text = '{"results": [{"index": 0, "category": "Nonsense"}, {"index": 9, "category": "Food"}, {"index": 1, "category": "Food"}]}'
    mapping = prompts.parse_classify_response(text, {0, 1})
    assert mapping == {1: "Food"}


def test_parse_classify_malformed_json_raises():
    with pytest.raises(ValueError):
        prompts.parse_classify_response("not json at all", {0})


def test_parse_classify_empty_results_raises():
    with pytest.raises(ValueError):
        prompts.parse_classify_response('{"results": []}', {0})


def test_parse_narrative_valid():
    text = '{"narrative": "All good.", "risk_level": "low"}'
    narrative, risk = prompts.parse_narrative_response(text)
    assert narrative == "All good."
    assert risk == "low"


def test_parse_narrative_invalid_risk_raises():
    with pytest.raises(ValueError):
        prompts.parse_narrative_response('{"narrative": "x", "risk_level": "extreme"}')


def test_stub_classifies_by_merchant():
    client = StubLLMClient()
    items = [
        ClassifyItem(index=0, merchant="Swiggy", notes=None, amount=100.0),
        ClassifyItem(index=1, merchant="Amazon", notes=None, amount=100.0),
        ClassifyItem(index=2, merchant="Unknown Shop", notes=None, amount=100.0),
    ]
    result = client.classify_batch(items)
    assert result.categories == {0: "Food", 1: "Shopping", 2: "Other"}
    assert not result.failed


def test_stub_summary_risk_scales_with_anomalies():
    client = StubLLMClient()
    assert client.summarize({"anomaly_count": 0}).risk_level == "low"
    assert client.summarize({"anomaly_count": 2}).risk_level == "medium"
    assert client.summarize({"anomaly_count": 8}).risk_level == "high"
