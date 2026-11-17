"""#6 结构化输出：JSON mode / response_format 支持。"""

from __future__ import annotations

import json

import pytest


def _req(model: str, response_format: dict, max_tokens: int = 4096) -> dict:
    return {
        "model": model,
        "messages": [{"role": "user", "content":
                      '请用 JSON 回答：{"name": "glm", "tags": ["a", "b"], "score": 9.5} 这个对象包含哪些键？'}],
        "max_tokens": max_tokens,
        "thinking": {"type": "enabled"},
        "response_format": response_format,
    }


def test_06_json_mode(client, rec):
    """response_format={"type":"json_object"}：响应必须是合法 JSON"""
    req = _req(client.model, {"type": "json_object"})
    result = client.chat(req)
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.expect("HTTP 2xx", result.ok, f"status={result.status_code} err={result.error}")
    try:
        parsed = json.loads(result.content)
        is_json = isinstance(parsed, (dict, list))
    except json.JSONDecodeError:
        is_json = False
    rec.expect("content 为合法 JSON", is_json,
               f"content[:200]={result.content[:200]!r}")


def test_06_json_schema(client, rec):
    """response_format 带 json_schema：输出应符合 schema（不支持则 4xx 记录为 soft）"""
    schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "person",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "age"],
            },
        },
    }
    req = _req(client.model, schema)
    req["messages"] = [{"role": "user", "content":
                        "生成一个虚构人物的信息，只需 JSON。"}]
    result = client.chat(req)
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    if result.status_code is not None and 400 <= result.status_code < 500:
        rec.check("json_schema 被支持", False,
                  f"端点拒绝 json_schema（status={result.status_code}），请人工确认是否要求支持", soft=True)
        return
    rec.expect("HTTP 2xx", result.ok, f"status={result.status_code} err={result.error}")
    try:
        parsed = json.loads(result.content)
        ok = isinstance(parsed, dict) and "name" in parsed and "age" in parsed
    except json.JSONDecodeError:
        ok = False
    rec.expect("输出符合 schema（含 name/age 键）", ok,
               f"content[:200]={result.content[:200]!r}")
