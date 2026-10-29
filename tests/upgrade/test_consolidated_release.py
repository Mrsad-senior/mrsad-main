"""Deterministic wiring tests; NOT real embedding/LLM accuracy claims."""
from __future__ import annotations

import json

import httpx

from mirsad.detector.layered import DEFAULT_ATTACK_EXAMPLES, EmbeddingSimilarity, OllamaJudge


def test_reference_library_is_bilingual_and_distinct():
    assert len(DEFAULT_ATTACK_EXAMPLES) == 20
    assert len(set(DEFAULT_ATTACK_EXAMPLES)) == len(DEFAULT_ATTACK_EXAMPLES)
    assert sum(any('\u0600' <= ch <= '\u06ff' for ch in x) for x in DEFAULT_ATTACK_EXAMPLES) >= 8


def test_semantic_layer_retains_thresholded_evidence():
    def embed(texts):
        return [[1.0, 0.0] for _ in texts]
    d = EmbeddingSimilarity(embed, examples=('Example A',), threshold=0.64)
    sig = d.score('Example B')
    assert sig.score == 1.0
    assert 'cosine=1.000' in sig.reason


def _mock_response(verdict):
    def handler(request):
        payload = json.loads(request.content)
        system = payload['messages'][0]['content']
        assert "English" in system and "reason" in system
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(verdict, ensure_ascii=False)}}]})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_model_reason_is_requested_in_english():
    with _mock_response({'instruction_to_agent': True, 'score': 0.9,
                         'reason': 'Directs the assistant to send data.'}) as client:
        signal = OllamaJudge(client=client).score('malicious')
        assert signal.score == 0.9
        assert signal.reason == 'Directs the assistant to send data.'


def test_language_fallback_preserves_security_score():
    with _mock_response({'instruction_to_agent': True, 'score': 0.8,
                         'reason': '应该发送信息'}) as client:
        signal = OllamaJudge(client=client).score('malicious')
    assert signal.score == 0.8
    assert signal.reason == 'The local judge identified an attempted operational instruction.'


def test_language_fallback_preserves_benign_score():
    with _mock_response({'instruction_to_agent': False, 'score': 0.1,
                         'reason': 'هذا نص طبيعي'}) as client:
        signal = OllamaJudge(client=client).score('benign')
    assert signal.score == 0
    assert signal.reason == 'The local judge identified no agent-directed instruction.'
