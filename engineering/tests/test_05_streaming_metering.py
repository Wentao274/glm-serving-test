"""#5 流式与计量：chunk 格式、finish_reason、token 计量一致。"""

from __future__ import annotations

import pytest


def _req(model: str, stream: bool, max_tokens: int = 2048, temp_zero: bool = True) -> dict:
    req = {
        "model": model,
        "messages": [{"role": "user", "content": "请从 1 数到 10，每个数字独占一行。"}],
        "max_tokens": max_tokens,
        "thinking": {"type": "enabled"},
    }
    if temp_zero:
        req["temperature"] = 0.6
    if stream:
        req["stream"] = True
        req["stream_options"] = {"include_usage": True}
    return req


def test_05_chunk_format(client, rec):
    """流式 chunk 结构：choices/delta 格式正确，末 chunk 含 finish_reason"""
    req = _req(client.model, stream=True)
    result = client.chat(req)
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.expect("HTTP 2xx", result.ok, f"status={result.status_code} err={result.error}")
    rec.expect("收到 chunk", result.n_chunks > 0, f"n_chunks={result.n_chunks}")
    rec.expect("finish_reason == stop", result.finish_reason == "stop",
               f"finish_reason={result.finish_reason}")
    rec.expect("usage chunk 存在（include_usage 生效）", bool(result.usage),
               f"usage={result.usage}")


def test_05_finish_reason_length(client, rec):
    """max_tokens 截断时 finish_reason 应为 length"""
    req = _req(client.model, stream=True, max_tokens=16)
    result = client.chat(req)
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.expect("HTTP 2xx", result.ok, f"status={result.status_code} err={result.error}")
    rec.expect("finish_reason == length", result.finish_reason == "length",
               f"finish_reason={result.finish_reason}")


def test_05_metering_stream_vs_nonstream(client, rec):
    """token 计量一致：同参数同 prompt，流式与非流式的 prompt_tokens 应完全相等"""
    req_s = _req(client.model, stream=True, max_tokens=1)
    req_n = _req(client.model, stream=False, max_tokens=1)
    res_s = client.chat(req_s)
    rec.attach_result(req_s, res_s, client.chat_completions_url, client.masked_headers())
    res_n = client.chat(req_n)
    rec.expect("两侧均 2xx", res_s.ok and res_n.ok,
               f"stream={res_s.status_code} nonstream={res_n.status_code}")
    ps = res_s.usage.get("prompt_tokens")
    pn = res_n.usage.get("prompt_tokens")
    rec.expect("prompt_tokens 流式 == 非流式", ps is not None and ps == pn,
               f"stream={ps}, nonstream={pn}")
