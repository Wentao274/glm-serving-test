#!/usr/bin/env python
"""GLM-5.3 供应商自测基线 — 功能兼容性验收测试主入口。

用法：
    python run_tests.py engineering [pytest 参数...]
    python run_tests.py engineering --base-url https://vendor.example.com/v1 \
        --api-key sk-xxx --model glm-5.3
    python run_tests.py engineering -k test_07 -x
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SUITES = {
    "engineering": "engineering/tests",
}


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        print("可用套件：")
        for name, path in SUITES.items():
            print(f"  {name:<12} -> {path}")
        return 0

    suite, rest = args[0], args[1:]
    if suite not in SUITES:
        print(f"错误：未知套件 '{suite}'。可用：{', '.join(SUITES)}")
        return 2

    try:
        import pytest
    except ImportError:
        print("错误：未安装 pytest。请先执行：pip install -r requirements.txt")
        return 2

    target = str(ROOT / SUITES[suite])
    pytest_args = [target, "-v", "--tb=short", *rest]
    print(f"[run_tests] suite={suite}\n[run_tests] pytest {' '.join(pytest_args)}\n")
    return pytest.main(pytest_args)


if __name__ == "__main__":
    sys.exit(main())
