"""前置冒烟检查（非验收条目）：/models、最小 chat、错误 key、未知模型。"""

from __future__ import annotations

import pytest


@pytest.mark.usefixtures("rec")
class TestSmokeConnectivity:
    def test_smoke_models_endpoint(self, client, rec):
        """GET /models 返回 200 且为 JSON 对象"""
        status, body, latency, error = client.get_models()
        rec.attach_raw("GET", client.models_url, client.masked_headers(), status, body, latency, error)
        rec.expect("GET /models 请求成功（无网络错误）", error is None, error or "")
        rec.expect("GET /models 返回 2xx", status is not None and 200 <= status < 300,
                   f"status={status}")
        import json
        try:
            is_obj = isinstance(json.loads(body), dict)
        except json.JSONDecodeError:
            is_obj = False
        rec.expect("响应为 JSON 对象", is_obj)

    def test_smoke_minimal_chat(self, client, rec):
        """最小 chat 请求返回 200，且 content/usage 结构完整"""
        req = {
            "model": client.model,
            "messages": [{"role": "user", "content": "Say OK and nothing else."}],
            "max_tokens": 1024,
            "thinking": {"type": "enabled"},
        }
        result = client.chat(req)
        rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
        rec.expect("HTTP 2xx", result.ok, f"status={result.status_code} err={result.error}")
        rec.expect("content 非空", bool(result.content.strip()),
                   f"content={result.content[:80]!r}")
        rec.expect("usage 包含 prompt_tokens/completion_tokens",
                   "prompt_tokens" in result.usage and "completion_tokens" in result.usage,
                   f"usage={result.usage}")

    def test_smoke_invalid_key_rejected(self, client, settings, rec):
        """错误 API key 应返回 401/403"""
        from engineering.core.client import VendorClient
        bad = VendorClient(settings.base_url, "sk-invalid-key-0000000000",
                           settings.model, timeout=60.0)
        req = {"model": settings.model,
               "messages": [{"role": "user", "content": "hi"}], "max_tokens": 8}
        result = bad.chat(req)
        rec.attach_result(req, result, bad.chat_completions_url, bad.masked_headers())
        rec.expect("返回 401/403", result.status_code in (401, 403),
                   f"status={result.status_code}")

    def test_smoke_unknown_model_rejected(self, client, rec):
        """未知模型名应返回 4xx"""
        req = {
            "model": "gst-definitely-not-exist-model-9z8x",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 8,
        }
        result = client.chat(req)
        rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
        rec.expect("返回 4xx", result.status_code is not None and 400 <= result.status_code < 500,
                   f"status={result.status_code}")
