#!/usr/bin/env python
"""GLM-5.3 供应商自测基线 — 功能兼容性验收测试主入口。

用法：
    python run_tests.py engineering [pytest 参数...]
    python run_tests.py engineering --base-url https://vendor.example.com/v1 \
        --api-key sk-xxx --model glm-5.3
    python run_tests.py engineering -k test_07 -x
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SUITES = {
    "engineering": "engineering/tests",
}


def _ensure_venv() -> None:
    """虚拟环境自举：存在 .venv 时切换至其解释器运行；不存在且 uv 可用时
    自动创建并安装依赖后切换，保证测试全周期在 uv 虚拟环境内运行。"""
    venv_dir = ROOT / ".venv"
    venv_py = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    current = Path(sys.executable).resolve()

    if not venv_py.exists():
        uv = shutil.which("uv")
        if not uv:
            return  # 无 uv：按当前解释器继续（依赖缺失时报清晰错误）
        print("[run_tests] 未发现 .venv，使用 uv 自动创建虚拟环境 ...", flush=True)
        subprocess.check_call([uv, "venv"], cwd=ROOT)
        subprocess.check_call([uv, "pip", "install", "-r", "requirements.txt"], cwd=ROOT)

    if current != venv_py.resolve():
        print(f"[run_tests] 切换至虚拟环境解释器: {venv_py}", flush=True)
        os.execv(str(venv_py), [str(venv_py), str(ROOT / "run_tests.py"), *sys.argv[1:]])


_ensure_venv()


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
