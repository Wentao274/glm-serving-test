"""#2 usage 字段：必须返回 prompt_tokens、completion_tokens、cached_tokens。"""

from __future__ import annotations

_REQUIRED = ("prompt_tokens", "completion_tokens", "cached_tokens")


def _req(model: str, stream: bool = False) -> dict:
    req = {
        "model": model,
        "messages": [{"role": "user", "content": "Say OK and nothing else."}],
        "max_tokens": 64,
        "thinking": {"type": "disabled"},
    }
    if stream:
        req["stream"] = True
        req["stream_options"] = {"include_usage": True}
    return req


def _check_usage(rec, usage: dict, label: str) -> None:
    missing = [k for k in _REQUIRED if k not in usage]
    rec.expect(f"{label} usage 含全部必需字段（{','.join(_REQUIRED)}）",
               not missing, f"missing={missing}; usage={usage}")
    for k in _REQUIRED:
        if k in usage:
            rec.expect(f"{label} {k} 为整数", isinstance(usage[k], int) and not isinstance(usage[k], bool),
                       f"{k}={usage[k]!r}")


def test_02_usage_fields_nonstream(client, rec):
    """非流式：usage 必须含 prompt_tokens/completion_tokens/cached_tokens"""
    req = _req(client.model)
    result = client.chat(req)
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.expect("HTTP 2xx", result.ok, f"status={result.status_code} err={result.error}")
    rec.expect("usage 存在", bool(result.usage), f"usage={result.usage}")
    _check_usage(rec, result.usage, "非流式")


def test_02_usage_fields_stream(client, rec):
    """流式（include_usage）：usage chunk 必须含同样三个字段"""
    req = _req(client.model, stream=True)
    result = client.chat(req)
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.expect("HTTP 2xx", result.ok, f"status={result.status_code} err={result.error}")
    rec.expect("流中含 usage chunk", bool(result.usage),
               "未收到 usage（要求 stream_options.include_usage 生效）")
    _check_usage(rec, result.usage, "流式")


def test_02_usage_fields_thinking_mode(client, rec):
    """thinking 模式下 usage 字段同样完整"""
    req = _req(client.model)
    req["thinking"] = {"type": "enabled"}
    result = client.chat(req)
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.expect("HTTP 2xx", result.ok, f"status={result.status_code} err={result.error}")
    _check_usage(rec, result.usage, "thinking 模式")
