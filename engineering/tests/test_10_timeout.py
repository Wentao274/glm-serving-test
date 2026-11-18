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


# 网关读超时上限判定常量
_ONE_HOUR_S = 3600          # 上限：允许 ≤1h，超过才截
_TOL_S = 3                  # 容忍窗口（±3s）：3597~3603 截止均判为"截于 1h"
_LOWER_S = _ONE_HOUR_S - _TOL_S
_UPPER_S = _ONE_HOUR_S + _TOL_S
_TARGET = 99_999_999        # 超大计数目标（由 cap 决定流时长）
_CAP_TOKENS = 131072        # 供应商 max_tokens 上限（build8 实测 [1, 131072]）


@pytest.mark.heavy
def test_10_one_hour_stream(client, rec, settings):
    """heavy：网关读超时上限为 1h（允许 ≤1h，超过才截；容忍窗 ±3s）。

    判定（实测时长均注明）：
    - 3597 ≤ 截止/自然结束 ≤ 3603（±3s 窗口内）→ 通过（截于 1h）；
    - <3597 因 cap 自然结束（finish=length/stop）→ SKIPPED 并注明：
      "未触达 1h 边界：流于 {t}s 因 completion 上限自然结束，上限 ≥ {t}s"；
    - <3597 被非自然断流（连接重置/5xx）→ 失败（提前中断）；
    - >3603 仍在流未被截断 → 失败（超过上限未被截断）。
    """
    if not settings.include_heavy:
        pytest.skip("需 --include-heavy 运行")
    req = _counting_req(client.model, _TARGET)
    req["max_tokens"] = _CAP_TOKENS
    started = time.monotonic()
    # 客户端超时须大于 3900 以便观测网关是否在 1h 处截断
    result = client.chat(req, timeout=_UPPER_S + 600)
    duration = time.monotonic() - started
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    completion = result.usage.get("completion_tokens", 0)
    rec.extra["duration_s"] = round(duration, 1)
    rec.extra["completion_tokens"] = completion
    rec.extra["finish_reason"] = result.finish_reason
    rec.extra["note"] = f"判定窗口：允许 ≤{_ONE_HOUR_S}s，超过才截；容忍 ±{_TOL_S}s"

    err = result.error
    err_text = str(err).lower() if err else ""
    is_timeout_cut = bool(err) and any(k in err_text for k in ("timeout", "timed out", "protocol", "read"))

    # 分支 1：<3597 因 cap 自然结束（注明未触达）
    if not err and result.finish_reason in ("length", "stop") and duration < _LOWER_S:
        pytest.skip(
            f"未触达 1h 边界：流于 {duration:.0f}s 因 completion 上限自然结束"
            f"(finish={result.finish_reason}, completion_tokens={completion})。"
            f"网关读超时上限 ≥ {duration:.0f}s；受 cap 限制无法直接观测 1h 边界"
        )

    # 分支 2：<3597 被非自然断流 → 失败
    if err and duration < _LOWER_S:
        rec.expect("3597s 前未被提前断流", False,
                   f"duration={duration:.1f}s 即断流（提前中断）: {err}")
        return

    # 分支 3：3597~3603 之间被截断或自然结束 → 通过（截于 1h）
    if _LOWER_S <= duration <= _UPPER_S:
        how = "被网关超时截断" if is_timeout_cut else "自然结束于 cap"
        rec.expect("网关读超时上限为 1h（3597~3603 窗口内截止/截断）", True,
                   f"duration={duration:.1f}s, {how}, finish={result.finish_reason}, "
                   f"completion_tokens={completion}")
        return

    # 分支 4：>3603 仍在流未被截断 → 失败
    rec.expect("超过 1h+容忍窗(3603s)未被截断",
               duration <= _UPPER_S,
               f"duration={duration:.1f}s 仍在流未被截断（超过上限未被截断）, "
               f"finish={result.finish_reason}, error={err}")
