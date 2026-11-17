#!/usr/bin/env bash
# 测试套件执行入口（Jenkins 与本地共用，仅 engineering）。
#
# 必需环境变量：SUITE / KST_BASE_URL / KST_API_KEY / KST_MODEL / KST_OUT_DIR
# 可选：ENG_FILTER / ENG_INCLUDE_HEAVY / OFFICIAL_BASE_URL / OFFICIAL_API_KEY / OFFICIAL_MODEL
set -u
cd "$(dirname "$0")/.."

# .venv 不存在且 uv 可用时自动创建并安装依赖，保证全周期在虚拟环境内运行
if [ ! -d ".venv" ]; then
    if command -v uv >/dev/null 2>&1; then
        echo "[run_suite] .venv 不存在，使用 uv 自动创建虚拟环境..."
        uv venv
        uv pip install -r requirements.txt
    else
        echo "[run_suite] 警告: .venv 不存在且未找到 uv，将使用系统 python 运行" >&2
    fi
fi
if [ -d ".venv" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

: "${SUITE:?missing SUITE}"
: "${KST_BASE_URL:?missing KST_BASE_URL}"
: "${KST_API_KEY:?missing KST_API_KEY}"
: "${KST_MODEL:?missing KST_MODEL}"
: "${KST_OUT_DIR:?missing KST_OUT_DIR}"
mkdir -p "${KST_OUT_DIR}"

if [ "${SUITE}" != "engineering" ]; then
    echo "未知 SUITE: ${SUITE}（本仓库仅支持 engineering）" >&2
    exit 2
fi

ARGS=(--base-url "${KST_BASE_URL}" --api-key "${KST_API_KEY}" --model "${KST_MODEL}"
      --report-dir "${KST_OUT_DIR}")

if [ -n "${ENG_FILTER:-}" ]; then
    ARGS=(-k "${ENG_FILTER}" "${ARGS[@]}")
fi
if [ "${ENG_INCLUDE_HEAVY:-false}" = "true" ]; then
    ARGS+=(--include-heavy)
fi
if [ -n "${OFFICIAL_BASE_URL:-}" ]; then
    ARGS+=(--official-base-url "${OFFICIAL_BASE_URL}")
fi
if [ -n "${OFFICIAL_API_KEY:-}" ]; then
    ARGS+=(--official-api-key "${OFFICIAL_API_KEY}")
fi
if [ -n "${OFFICIAL_MODEL:-}" ]; then
    ARGS+=(--official-model "${OFFICIAL_MODEL}")
fi

echo "[run_suite] python run_tests.py ${SUITE} ${ARGS[*]}"
RC=0
python run_tests.py "${SUITE}" "${ARGS[@]}" || RC=$?

python scripts/gen_stats.py "${KST_OUT_DIR}" "${SUITE}" "${RC}"
echo "[run_suite] suite=${SUITE} exit_code=${RC}"
exit "${RC}"
