"""#10 超时时间：模型最长返回时长 1 小时。

- test_10_long_stream_alive：中等时长（数分钟）流式生成不断流（日常校验）；
- test_10_one_hour_stream（heavy）：单响应可持续 1 小时不被中断（--include-heavy）。
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


# 按 GLM 基线 TPOT(~14ms,约 70 tokens/s)估算：1 小时 ≈ 25 万 tokens，
# 计数到 200000(约 70 万 tokens)足以覆盖 1 小时生成；max_tokens 取 262144(≈1h 生成量)
_ONE_HOUR_S = 3600
_TARGET = 200000
_MAX_TOKENS_FOR_1H = 262144


@pytest.mark.heavy
def test_10_one_hour_stream(client, rec, settings):
    """heavy：单响应可持续 1 小时不被中断。

    判定口径：
    - 流活动（持续有 chunk）≥ 3600s 且无连接错误/中断 → 通过；
    - 流在 3600s 前因 completion 上限/模型收尾而提前结束 → 记"无法验证"
      （单响应 1h 连续性未被检验到，不构成供应商失败，需确认其 completion 上限）；
    - 中途连接错误/超时/断流 → 失败。
    """
    if not settings.include_heavy:
        pytest.skip("需 --include-heavy 运行")
    req = _counting_req(client.model, _TARGET)
    req["max_tokens"] = _MAX_TOKENS_FOR_1H
    started = time.monotonic()
    result = client.chat(req, timeout=75 * 60)
    duration = time.monotonic() - started
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.extra["duration_s"] = round(duration, 1)
    completion = result.usage.get("completion_tokens", 0)
    rec.extra["completion_tokens"] = completion

    rec.expect("无中途连接错误/中断", result.error is None,
               f"status={result.status_code} error={result.error}")
    rec.expect("HTTP 2xx", result.ok, f"status={result.status_code} err={result.error}")

    if result.finish_reason in ("length", "stop") and duration < _ONE_HOUR_S:
        pytest.skip(
            f"无法验证 1 小时连续性：流于 {duration:.0f}s 提前结束"
            f"(finish={result.finish_reason}, completion_tokens={completion})。"
            "单响应 1 小时不被中断未被检验到——需确认供应商 completion 上限是否 ≥ 1h 生成量"
        )

    rec.expect("单响应持续 1 小时不被中断（流活动 ≥ 3600s）",
               duration >= _ONE_HOUR_S and result.n_chunks > 0,
               f"duration={duration:.1f}s, finish={result.finish_reason}, "
               f"n_chunks={result.n_chunks}, completion_tokens={completion}")
