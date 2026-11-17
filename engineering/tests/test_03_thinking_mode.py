"""#3 thinking 模式：支持 thinking:{type:"enabled"/"disabled"} 切换。"""

from __future__ import annotations

_REASONING_MSG = [{"role": "user", "content":
                   "鸡兔同笼，共有 35 个头，94 只脚。请计算鸡和兔各有多少只。"}]


def _req(model: str, thinking: dict, stream: bool = False) -> dict:
    req = {"model": model, "messages": _REASONING_MSG, "max_tokens": 4096,
           "thinking": thinking}
    if stream:
        req["stream"] = True
        req["stream_options"] = {"include_usage": True}
    return req


def test_03_thinking_enabled(client, rec):
    """thinking.type=enabled：响应应含 reasoning_content"""
    req = _req(client.model, {"type": "enabled"})
    result = client.chat(req)
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.expect("HTTP 2xx", result.ok, f"status={result.status_code} err={result.error}")
    rec.expect("reasoning_content 非空", bool(result.reasoning_content.strip()),
               f"len={len(result.reasoning_content)}")
    rec.expect("content 非空", bool(result.content.strip()))


def test_03_thinking_disabled(client, rec):
    """thinking.type=disabled：响应不应含 reasoning_content"""
    req = _req(client.model, {"type": "disabled"}, stream=False)
    result = client.chat(req)
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.expect("HTTP 2xx", result.ok, f"status={result.status_code} err={result.error}")
    rec.expect("reasoning_content 为空", not result.reasoning_content.strip(),
               f"len={len(result.reasoning_content)}")
    rec.expect("content 非空", bool(result.content.strip()))


def test_03_thinking_enabled_stream(client, rec):
    """流式 + enabled：reasoning chunk 与 content chunk 均出现"""
    req = _req(client.model, {"type": "enabled"}, stream=True)
    result = client.chat(req)
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.expect("HTTP 2xx", result.ok, f"status={result.status_code} err={result.error}")
    rec.expect("流中含 reasoning_content", bool(result.reasoning_content.strip()))
    rec.expect("流中含 content", bool(result.content.strip()))
    rec.expect("finish_reason == stop", result.finish_reason == "stop",
               f"finish_reason={result.finish_reason}")
