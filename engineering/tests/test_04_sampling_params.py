"""#4 采样参数：temperature / top_p / max_tokens 行为与原厂一致。"""

from __future__ import annotations

import pytest

_PROMPT = [{"role": "user", "content": "Say 'OK' and nothing else."}]


def _req(model: str, extra: dict | None = None) -> dict:
    req = {"model": model, "messages": _PROMPT, "max_tokens": 32,
           "thinking": {"type": "disabled"}}
    if extra:
        req.update(extra)
    return req


@pytest.mark.parametrize("param,value", [("temperature", 0.6), ("temperature", 1.0),
                                         ("top_p", 0.95), ("top_p", 0.8)],
                         ids=["t=0.6", "t=1.0", "p=0.95", "p=0.8"])
def test_04_sampling_param_accepted(client, rec, param, value):
    """temperature/top_p 常规取值应被接受"""
    req = _req(client.model, {param: value})
    result = client.chat(req)
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.expect(f"{param}={value} 被接受（HTTP 2xx）", result.ok,
               f"status={result.status_code} err={result.error}")


def test_04_max_tokens_respected(client, rec):
    """max_tokens 小值应精确生效（completion ≤ 上限且 finish=length）"""
    req = _req(client.model, {"max_tokens": 48})
    req["messages"] = [{"role": "user", "content": "请从 1 数到 500，每个数字独占一行。"}]
    result = client.chat(req)
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.expect("HTTP 2xx", result.ok, f"status={result.status_code} err={result.error}")
    completion = result.usage.get("completion_tokens", 0)
    rec.expect("completion_tokens ≤ 48（小上限生效）", 0 < completion <= 48,
               f"completion_tokens={completion}, finish={result.finish_reason}")


def _top_logprobs(result) -> list | None:
    data = result.response_json or {}
    choices = data.get("choices") or []
    if not choices:
        return None
    content = (choices[0].get("logprobs") or {}).get("content") or []
    return content[0].get("top_logprobs") if content else None


@pytest.mark.parametrize("extra", [{"temperature": 0.6}, {"temperature": 1.0}],
                         ids=["t=0.6", "t=1.0"])
def test_04_distribution_vs_official(client, rec, official_client, settings, extra):
    """与原厂对照：同 prompt 同参数的首 token 分布应一致（需 --official-*）"""
    if official_client is None:
        pytest.skip("未配置 --official-base-url/--official-api-key/--official-model")
    req_v = _req(client.model, {**extra, "logprobs": True, "top_logprobs": 5, "max_tokens": 1})
    req_o = _req(settings.official_model, {**extra, "logprobs": True, "top_logprobs": 5, "max_tokens": 1})
    res_v = client.chat(req_v)
    rec.attach_result(req_v, res_v, client.chat_completions_url, client.masked_headers())
    rec.expect("供应商请求 2xx", res_v.ok)
    res_o = official_client.chat(req_o)
    rec.expect("原厂请求 2xx", res_o.ok)
    lp_v, lp_o = _top_logprobs(res_v), _top_logprobs(res_o)
    if lp_v is None or lp_o is None:
        rec.check("两侧均返回 logprobs", False, "一侧不支持 logprobs", soft=True)
        pytest.skip("一侧不支持 logprobs，无法做分布对照")
    rec.extra["vendor_top_logprobs"] = lp_v
    rec.extra["official_top_logprobs"] = lp_o
    tokens_v = [t.get("token") for t in lp_v]
    tokens_o = [t.get("token") for t in lp_o]
    rec.expect(f"{extra} 首 token top_logprobs 序列与原厂一致", tokens_v == tokens_o,
               f"vendor={tokens_v} vs official={tokens_o}")


def test_04_max_tokens_behavior_vs_official(client, rec, official_client, settings):
    """与原厂对照：相同 max_tokens 上限的截断行为应一致（需 --official-*）"""
    if official_client is None:
        pytest.skip("未配置 --official-base-url/--official-api-key/--official-model")
    prompt = [{"role": "user", "content": "请从 1 数到 500，每个数字独占一行。"}]
    req_v = {"model": client.model, "messages": prompt, "max_tokens": 48,
             "thinking": {"type": "disabled"}}
    req_o = {"model": settings.official_model, "messages": prompt, "max_tokens": 48,
             "thinking": {"type": "disabled"}}
    res_v = client.chat(req_v)
    rec.attach_result(req_v, res_v, client.chat_completions_url, client.masked_headers())
    res_o = official_client.chat(req_o)
    rec.expect("两侧均 2xx", res_v.ok and res_o.ok,
               f"vendor={res_v.status_code} official={res_o.status_code}")
    cv = res_v.usage.get("completion_tokens", 0)
    co = res_o.usage.get("completion_tokens", 0)
    rec.expect("completion_tokens 均 ≤ 48（两侧截断一致）",
               0 < cv <= 48 and 0 < co <= 48, f"vendor={cv}, official={co}")
    rec.check("finish_reason 两侧一致（均应为 length）",
              res_v.finish_reason == res_o.finish_reason,
              f"vendor={res_v.finish_reason}, official={res_o.finish_reason}", soft=True)
