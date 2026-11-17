"""#1 协议格式：OpenAI Chat Completions 兼容，stream SSE 格式。"""

from __future__ import annotations

import pytest


def _req(model: str, stream: bool = False) -> dict:
    req = {
        "model": model,
        "messages": [{"role": "user", "content": "Say OK and nothing else."}],
        "max_tokens": 64,
        "thinking": {"type": "enabled"},
    }
    if stream:
        req["stream"] = True
        req["stream_options"] = {"include_usage": True}
    return req


def test_01_nonstream_response_format(client, rec):
    """非流式响应为合法的 chat.completion 结构"""
    req = _req(client.model)
    result = client.chat(req)
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.expect("HTTP 2xx", result.ok, f"status={result.status_code} err={result.error}")
    data = result.response_json or {}
    rec.expect("object == 'chat.completion'", data.get("object") == "chat.completion",
               f"object={data.get('object')!r}")
    rec.expect("含 id 字段且非空", bool(data.get("id")), f"id={data.get('id')!r}")
    choices = data.get("choices") or []
    rec.expect("choices 非空", bool(choices))
    msg = (choices[0].get("message") or {}) if choices else {}
    rec.expect("message.role == 'assistant'", msg.get("role") == "assistant",
               f"role={msg.get('role')!r}")
    rec.expect("finish_reason 存在", choices[0].get("finish_reason") is not None if choices else False,
               f"finish_reason={choices[0].get('finish_reason') if choices else None}")


def test_01_stream_sse_format(client, rec):
    """流式响应为合法 SSE：chat.completion.chunk 序列 + [DONE] 结束"""
    req = _req(client.model, stream=True)
    result = client.chat(req)
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.expect("HTTP 2xx", result.ok, f"status={result.status_code} err={result.error}")
    ctype = (result.response_headers.get("content-type") or "").lower()
    rec.expect("Content-Type 为 text/event-stream", "text/event-stream" in ctype,
               f"content-type={ctype}")
    rec.expect("收到 SSE chunk", result.n_chunks > 0, f"n_chunks={result.n_chunks}")
    rec.expect("SSE 以 [DONE] 结束", "[DONE]" in result.raw_text[-64:],
               f"tail={result.raw_text[-64:]!r}")
    rec.expect("chunk 重组后含 content", bool(result.content.strip()),
               "SSE chunk 未重组出 content")
    rec.expect("finish_reason 存在于末 chunk", result.finish_reason is not None,
               f"finish_reason={result.finish_reason}")
