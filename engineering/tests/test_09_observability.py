"""#9 可观测性：返回 request_id，可用于问题追溯。"""

from __future__ import annotations


def _req(model: str) -> dict:
    return {
        "model": model,
        "messages": [{"role": "user", "content": "Say OK and nothing else."}],
        "max_tokens": 16,
        "thinking": {"type": "disabled"},
    }


def _find_request_id(result) -> list[str]:
    """在响应体 id 字段与响应头中寻找 request 标识。"""
    hits = []
    body = result.response_json or {}
    if body.get("id"):
        hits.append(f"body:id={body['id']}")
    headers = {k.lower(): v for k, v in (result.response_headers or {}).items()}
    for key in headers:
        if "trace" in key or ("request" in key and "id" in key):
            hits.append(f"header:{key}={headers[key]}")
    return hits


def test_09_request_id_in_body(client, rec):
    """响应体应含非空 id 字段（chat completion id）"""
    req = _req(client.model)
    result = client.chat(req)
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.expect("HTTP 2xx", result.ok, f"status={result.status_code} err={result.error}")
    rid = (result.response_json or {}).get("id")
    rec.expect("响应体含非空 id 字段（可追溯的 request_id）", bool(rid),
               f"id={rid!r}")


def test_09_request_id_header(client, rec):
    """响应头中的 request 标识（soft：记录命中情况供追溯验证）"""
    req = _req(client.model)
    result = client.chat(req)
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.expect("HTTP 2xx", result.ok, f"status={result.status_code} err={result.error}")
    hits = _find_request_id(result)
    rec.check("发现 request 标识（body id 或 header）", bool(hits),
              f"命中={hits or '无'}", soft=True)
    rec.extra["request_id_hits"] = hits
