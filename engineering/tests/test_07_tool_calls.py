"""#7 工具调用：Tool Call 单/多/并行，参数格式与原厂一致。"""

from __future__ import annotations

import json

import pytest

_WEATHER = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "查询指定城市的天气。",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "城市名"}},
            "required": ["city"],
        },
    },
}
_STOCK = {
    "type": "function",
    "function": {
        "name": "get_stock_price",
        "description": "查询指定股票代码的最新价格。",
        "parameters": {
            "type": "object",
            "properties": {"symbol": {"type": "string", "description": "股票代码"}},
            "required": ["symbol"],
        },
    },
}
_TOOLS = [_WEATHER, _STOCK]


def _valid_tcs(tool_calls: list) -> tuple[bool, str]:
    if not tool_calls:
        return False, "tool_calls 为空"
    for tc in tool_calls:
        fn = (tc or {}).get("function") or {}
        if not fn.get("name"):
            return False, f"缺少 function.name: {tc}"
        args = fn.get("arguments", "")
        if isinstance(args, str) and args:
            try:
                json.loads(args)
            except json.JSONDecodeError as exc:
                return False, f"arguments 非合法 JSON: {exc}"
    return True, ""


def test_07_single_tool_call(client, rec):
    """单工具调用：tool_choice 指定函数，应返回该函数的合法 tool_call"""
    req = {
        "model": client.model,
        "messages": [{"role": "user", "content": "北京今天天气怎么样？"}],
        "tools": _TOOLS,
        "tool_choice": {"type": "function", "function": {"name": "get_weather"}},
        "max_tokens": 1024,
        "thinking": {"type": "enabled"},
    }
    result = client.chat(req)
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.expect("HTTP 2xx", result.ok, f"status={result.status_code} err={result.error}")
    rec.expect("finish_reason == tool_calls", result.finish_reason == "tool_calls",
               f"finish_reason={result.finish_reason}")
    ok, msg = _valid_tcs(result.tool_calls)
    rec.expect("tool_calls 结构合法", ok, msg)
    name = result.tool_calls[0].get("function", {}).get("name") if result.tool_calls else None
    rec.expect("调用的是 get_weather", name == "get_weather", f"name={name}")
    args = json.loads(result.tool_calls[0]["function"]["arguments"]) if result.tool_calls else {}
    rec.expect("arguments 含 city 参数", "city" in args, f"args={args}")


def test_07_multi_tools_available(client, rec):
    """多工具可用：模型应从多个工具中选择并返回结构合法的 tool_call"""
    req = {
        "model": client.model,
        "messages": [{"role": "user", "content": "帮我查一下 600519 的最新价格。"}],
        "tools": _TOOLS,
        "tool_choice": "auto",
        "max_tokens": 1024,
        "thinking": {"type": "enabled"},
    }
    result = client.chat(req)
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.expect("HTTP 2xx", result.ok, f"status={result.status_code} err={result.error}")
    rec.expect("finish_reason == tool_calls", result.finish_reason == "tool_calls",
               f"finish_reason={result.finish_reason}")
    ok, msg = _valid_tcs(result.tool_calls)
    rec.expect("tool_calls 结构合法", ok, msg)
    name = result.tool_calls[0].get("function", {}).get("name") if result.tool_calls else None
    rec.check("选择了 get_stock_price（期望选择）", name == "get_stock_price",
              f"name={name}", soft=True)


def test_07_parallel_tool_calls(client, rec):
    """并行工具调用：需要两个工具的提问应返回 ≥2 个 tool_calls"""
    req = {
        "model": client.model,
        "messages": [{"role": "user", "content":
                      "请同时查询：1) 上海的天气；2) 600519 的价格。两个都要查。"}],
        "tools": _TOOLS,
        "tool_choice": "auto",
        "max_tokens": 2048,
        "thinking": {"type": "enabled"},
    }
    result = client.chat(req)
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.expect("HTTP 2xx", result.ok, f"status={result.status_code} err={result.error}")
    rec.expect("finish_reason == tool_calls", result.finish_reason == "tool_calls",
               f"finish_reason={result.finish_reason}")
    ok, msg = _valid_tcs(result.tool_calls)
    rec.expect("tool_calls 结构合法", ok, msg)
    rec.expect("并行返回 ≥2 个 tool_calls", len(result.tool_calls) >= 2,
               f"n={len(result.tool_calls)}")


def test_07_tool_call_stream(client, rec):
    """流式 tool call：tool_calls 分片应能重组为完整结构"""
    req = {
        "model": client.model,
        "messages": [{"role": "user", "content": "北京今天天气怎么样？"}],
        "tools": _TOOLS,
        "tool_choice": "auto",
        "max_tokens": 1024,
        "thinking": {"type": "enabled"},
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    result = client.chat(req)
    rec.attach_result(req, result, client.chat_completions_url, client.masked_headers())
    rec.expect("HTTP 2xx", result.ok, f"status={result.status_code} err={result.error}")
    rec.expect("finish_reason == tool_calls", result.finish_reason == "tool_calls",
               f"finish_reason={result.finish_reason}")
    ok, msg = _valid_tcs(result.tool_calls)
    rec.expect("流式重组的 tool_calls 结构合法", ok, msg)
