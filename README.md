# glm-serving-test

GLM-5.3 供应商自测基线 — **功能兼容性验收**测试工程（依据《GLM-5.3 供应商自测基线标准》「四、功能兼容性要求」10 个测试点实现）。

## 目录结构

```
├── run_tests.py            # 主入口（python run_tests.py engineering）
├── requirements.txt        # httpx + pytest
├── Jenkinsfile             # Jenkins 远程触发流水线（仅 engineering，含原厂对比）
├── scripts/                # 触发层辅助（run_suite.sh 参数透传 / gen_stats.py 统计 / gen_compare.py 对比）
├── engineering/            # 功能兼容性验收（10 个测试点）
│   ├── core/               #   框架：配置 / HTTP 客户端 / 用例记录 / HTML 报告
│   └── tests/              #   test_00 冒烟 + test_01~test_10（编号 = 需求测试点序号）
└── reports/                # 测试报告输出（gitignore）
```

## 环境准备

```bash
# 安装 uv（已装可跳过）：Windows PowerShell
irm https://astral.sh/uv/install.ps1 | iex
uv venv --python 3.11
.\.venv\Scripts\Activate.ps1        # Linux/Mac: source .venv/bin/activate
uv pip install -r requirements.txt
```

> **虚拟环境自举（无需手动建环境）**：只要系统有 uv，`run_tests.py` 与 `scripts/run_suite.sh` 会在 .venv 不存在时**自动创建并安装依赖、切换至 venv 解释器运行**——手动执行与 Jenkins 执行全周期均在 uv 虚拟环境内，不会落到系统 Python。

通用配置：CLI 参数或环境变量 `KST_BASE_URL` / `KST_API_KEY` / `KST_MODEL`。

## 快速开始

```bash
python run_tests.py engineering \
    --base-url https://vendor.example.com/v1 \
    --api-key sk-xxx \
    --model glm-5.3
```

报告自动生成于 `reports/engineering_<时间戳>/`：`report.html`（汇总 + 每用例请求/响应/断言/curl 复现命令，可过滤搜索）+ `report_data.json`。

## 验收覆盖项（对齐《GLM-5.3 供应商自测基线标准》四、功能兼容性要求）

| 模块 | 测试点 | 验收内容 |
|---|---|---|
| test_00_smoke_connectivity | （前置冒烟） | /models、最小 chat、错误 key 401/403、未知模型 4xx |
| test_01_protocol_format | #1 协议格式 | 非流式 chat.completion 结构完整；流式 SSE（text/event-stream、chunk 序列、[DONE]） |
| test_02_usage_fields | #2 usage 字段 | 非流式/流式/thinking 三场景 usage 含 prompt_tokens、completion_tokens、cached_tokens 且为整数 |
| test_03_thinking_mode | #3 thinking 模式 | enabled 含 reasoning_content；disabled 不含；流式两类 chunk |
| test_04_sampling_params | #4 采样参数 | temperature/top_p 接受性；max_tokens 小值精确生效；配置 `--official-*` 后 logprobs 分布与截断行为对照原厂 |
| test_05_streaming_metering | #5 流式与计量 | chunk 结构、finish_reason（stop/length）、流式与非流式 prompt_tokens 完全一致 |
| test_06_structured_output | #6 结构化输出 | json_object 输出合法 JSON；json_schema 符合 schema（不支持则 soft 记录） |
| test_07_tool_calls | #7 工具调用 | 单工具指定调用、多工具选择、并行 ≥2 tool_calls、流式分片重组、arguments 合法 JSON |
| test_08_error_codes | #8 错误码 | 401（错误 key）、400（非法参数）语义与结构化 error 体；429 突发观察（未限流则 soft 记录容量） |
| test_09_observability | #9 可观测性 | 响应体含非空 id；响应头 request 标识命中检查（soft） |
| test_10_timeout | #10 超时时间 | 数分钟流式不断流（日常）；完整 1 小时流式保活（`--include-heavy`） |

### 常用选项

```
--timeout 600             单请求读超时（秒）
--include-heavy           运行 #10 完整 1 小时流式保活验证
--official-base-url/--official-api-key/--official-model   #4 采样参数原厂对照（可选）
--report-dir DIR          报告输出目录（默认 reports/）
```

**原厂（智谱官方）对照配置示例**：

```bash
--official-base-url https://open.bigmodel.cn/api/paas/v4 \
--official-api-key <智谱 API Key> \
--official-model <原厂模型 id>
```

> URL 兼容说明：框架自动归一化 base url——已含版本路径（`/v1`、`/v4`）原样保留，否则补 `/v1`；误填完整端点 `.../chat/completions` 也会自动剥到 base（客户端同步兼容）。因此智谱的 `/api/paas/v4` 直接可用，无需手工改造。

## Jenkins 远程触发

根目录 `Jenkinsfile` 为声明式流水线（仅 engineering 套件）：

- **参数**:`TESTER`/`MODEL`/`BASE_URL`/`API_KEY`/`ENG_FILTER`(-k 过滤）/`INCLUDE_HEAVY`/`OFFICIAL_*`/`COMPARE_OFFICIAL`（原厂双跑对比，默认关）/`COMPARE_FILTER`（对比范围）
- **流程**：打印参数 → API 连通性预检（失败即终止）→ 环境检查（清残留 / git pull 记录代码版本 / uv venv）→ 运行验收 → （可选）原厂渠道对比执行 → 报告拉取 → 邮件（正文汇总统计 + 对比汇总，report.html 原格式附件；git pull 失败醒目告警）→ 保留最近 20 构建
- **输出**：远程机 `builds/engineering/<tester>/<model>/<构建号>/`

### Jenkins job 配置（一次性）

1. 新建 **Pipeline** job → **Pipeline script from SCM**：填本仓库地址与凭据，Script Path 填 `Jenkinsfile`；
2. 勾选「**触发远程构建**」并设置 Authentication Token（如 `gst-trigger-token`）。

### 远程触发命令

```bash
curl -X POST "https://<jenkins>/job/<job-name>/buildWithParameters?token=gst-trigger-token" \
    --user "<user>:<api-token>" \
    --data-urlencode "MODEL=glm-5.3" \
    --data-urlencode "BASE_URL=https://vendor.example.com" \
    --data-urlencode "API_KEY=sk-xxx" \
    --data-urlencode "TESTER=liwt"
```

> 本地脚本 `scripts/run_suite.sh` + `scripts/gen_stats.py` 与 Jenkins 解耦，可在任意 Linux 机器手动 `export` 环境变量后执行同一入口。

## 注意

- #4 采样参数"与原厂一致"类用例需配置 `OFFICIAL_*` 才执行对照，未配置时以 SKIPPED 标注（其余用例不受影响）。
- #8 的 429 语义依赖供应商限流阈值，突发 30 并发未触发限流时以 soft 记录容量信息，不算失败。
- 本工程仅覆盖「四、功能兼容性要求」;TTFT/TPOT 基线、缓存基线、开源评测集不在本工程范围。
