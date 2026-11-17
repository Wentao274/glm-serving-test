"""#8 错误码：429（限流）/ 401（认证）/ 400（参数）语义与原厂一致。"""

from __future__ import annotations

import json
import threading

import pytest

from engineering.core.client import VendorClient


def _req(model: str, **kw) -> dict:
    req = {"model": model,
           "messages": [{"role": "user", "content": "Say OK and nothing else."}],
           "max_tokens": 16,
           "thinking": {"type": "enabled"}}
    req.update(kw)
    return req


def _has_error_body(result) -> tuple[bool, str]:
    """错误响应应含结构化 error 信息。"""
    body = result.raw_text or ""
    try:
        data = json.loads(body)
        err = data.get("error")
        if isinstance(err, dict) and (err.get("message") or err.get("type")):
            return True, ""
        if isinstance(data.get("message"), str):
            return True, ""
    except json.JSONDecodeError:
        pass
    return False, body[:200]


def test_08_error_401(client, settings, rec):
    """错误 API key → 401（认证错误语义）"""
    bad = VendorClient(settings.base_url, "sk-invalid-key-0000000000",
                       settings.model, timeout=60.0)
    req = _req(settings.model)
    result = bad.chat(req)
    rec.attach_result(req, result, bad.chat_completions_url, bad.masked_headers())
    rec.expect("返回 401/403", result.status_code in (401, 403),
                   f"status={result.status_code}")
    ok, msg = _has_error_body(result)
    rec.check("错误响应含结构化 error 信息", ok, msg, soft=True)


def test_08_error_400(client, rec):
    """非法参数（temperature 超范围）→ 400（参数错误语义）"""
    req = _req(client.model, temperature=99)
    result = client.chat(req)
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.expect("返回 400", result.status_code is not None and result.status_code == 400,
               f"status={result.status_code}")
    ok, msg = _has_error_body(result)
    rec.check("错误响应含结构化 error 信息", ok, msg, soft=True)


def test_08_error_400_bad_max_tokens(client, rec):
    """非法 max_tokens（负数）→ 400"""
    req = _req(client.model, max_tokens=-5)
    result = client.chat(req)
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.expect("返回 400", result.status_code is not None and result.status_code == 400,
               f"status={result.status_code}")


def test_08_error_429_burst(client, rec, settings):
    """并发突发：观察 429（限流）语义；未触发限流则记录容量信息（soft）"""
    n = 30
    results = []
    lock = threading.Lock()

    def fire():
        c = VendorClient(settings.base_url, settings.api_key, settings.model, timeout=60.0)
        r = c.chat(_req(client.model))
        with lock:
            results.append(r)

    threads = [threading.Thread(target=fire) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    codes = {}
    first429 = None
    for r in results:
        codes[r.status_code] = codes.get(r.status_code, 0) + 1
        if r.status_code == 429 and first429 is None:
            first429 = r
    rec.attach_result(_req(client.model), first429 or results[0],
                      client.chat_completions_url, client.masked_headers())
    rec.extra["burst_status_distribution"] = codes
    rec.expect(f"{n} 并发请求均有响应（无连接层错误）",
               all(r.status_code is not None for r in results),
               f"分布={codes}")
    if 429 in codes:
        ok, msg = _has_error_body(first429)
        rec.expect("429 响应含结构化 error 信息", ok, msg)
    else:
        rec.check("触发限流并返回 429", False,
                  f"{n} 并发未触发限流（容量充足），429 语义未验证", soft=True)
