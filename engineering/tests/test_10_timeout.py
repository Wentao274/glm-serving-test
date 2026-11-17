"""#10 超时时间：模型最长返回时长 1 小时。

- test_10_long_stream_alive：中等时长（数分钟）流式生成不断流（日常校验）；
- test_10_one_hour_stream（heavy）：完整 1 小时流式连接保活验证（--include-heavy）。
"""

from __future__ import annotations

import time

import pytest


def _counting_req(model: str, target: int) -> dict:
    return {
        "model": model,
        "messages": [{"role": "user", "content":
                      f"请从 1 开始数到 {target}，每个数字独占一行，不要输出任何其他内容，中途不要停止。"}],
        "thinking": {"type": "enabled"},
        "temperature": 0.6,
        "stream": True,
        "stream_options": {"include_usage": True},
    }


def test_10_long_stream_alive(client, rec):
    """数分钟级流式生成：连接不中断、无中途超时（日常校验）"""
    req = _counting_req(client.model, 2000)
    started = time.monotonic()
    result = client.chat(req, timeout=1800)
    duration = time.monotonic() - started
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.extra["duration_s"] = round(duration, 1)
    rec.expect("HTTP 2xx", result.ok, f"status={result.status_code} err={result.error}")
    rec.expect("流式收到内容（连接保活）", bool(result.content.strip()),
               f"n_chunks={result.n_chunks}, duration={duration:.1f}s")
    rec.expect("finish_reason 存在（流正常收尾）", result.finish_reason is not None,
               f"finish_reason={result.finish_reason}")


@pytest.mark.heavy
def test_10_one_hour_stream(client, rec, settings):
    """heavy：完整 1 小时流式连接保活（对应"最长返回时长 1 小时"）"""
    if not settings.include_heavy:
        pytest.skip("需 --include-heavy 运行")
    req = _counting_req(client.model, 100000)
    started = time.monotonic()
    # 保持流式读取 1 小时；超时上限 75 分钟
    result = client.chat(req, timeout=75 * 60)
    duration = time.monotonic() - started
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.extra["duration_s"] = round(duration, 1)
    rec.expect("HTTP 2xx", result.ok, f"status={result.status_code} err={result.error}")
    rec.expect("流式连接保活满 1 小时（duration ≥ 3600s 或正常完成）",
               duration >= 3600 or result.finish_reason is not None,
               f"duration={duration:.1f}s, finish={result.finish_reason}, n_chunks={result.n_chunks}")
    rec.expect("无中途连接错误", result.error is None, f"error={result.error}")
