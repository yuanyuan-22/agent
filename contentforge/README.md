# ContentForge · 多智能体内容策划与分镜 Agent

> 从「源链接/完整文案 → 事实摘要 → 原创选题 → 短片脚本 → 分镜 → 质量审核 → 人工审核 → 内容资产包」的工作流，
> 由 **LangGraph** 编排。视频渲染保留为审核通过后的可选能力，不再以自动生成高质量成片为核心目标。

> 开发引导与决策背景见 `引导.md` / `PROJECT_CONTEXT.md`。

---

## 1. 它解决什么问题

做内容运营最耗人的是"理解素材 → 找角度 → 写脚本 → 做分镜 → 多平台复用 → 复盘"。本项目把源内容转换成可审阅、可编辑、可复用的**内容资产包**：

- 导入 B站/抖音/快手/小红书链接；页面被风控时使用完整分享文案兜底，仍无有效内容则要求人工补录。
- AnalystAgent 提取主题、事实点和传播结构；无来源依据时禁止进入创作。
- IdeationAgent 生成 3 个保持原主题的原创短片角度。
- WriterAgent 和 DirectorAgent 产出主脚本、字幕、镜头、画面提示词和配音文案。
- ReviewerAgent 检查主题一致性、事实支撑、原创性和合规性，不合格时带意见打回。
- 人工审核通过后输出 `asset_pack.json` 与 `content_assets.md`；如需视频，再手动触发可选渲染。
- 发布后的数据进入经验库，供后续写作检索引用。

---

## 2. 架构

```
┌───────────────────────────── LangGraph StateGraph ─────────────────────────────┐
│ START → fetch(链接/分享文案/人工文案) → insight(事实与内容洞察)                │
│        → ideate(3个原创角度) → write(原创脚本) → director(分镜)                │
│        → review(规则+LLM judge)                                                │
│                          │ 不过且次数<2            │ 通过 / 耗尽(带人工复核标记)  │
│                          ▼                        ▼                              │
│                        write ◀──(带feedback)── pack_assets(资产包) → END        │
│                                                                               │
│ 审核通过后可选： render(AI图/本地素材/讲解员/TTS/字幕/ffmpeg) → 发布包          │
└─────────────────────────────────────────────────────────────────────────────────┘
   │ 短期记忆: LangGraph SqliteSaver(checkpoint, thread_id=job_id, 可续跑/可查)
   │ 长期记忆: 向量经验库(bge-m3 embedding + 余弦检索)  ← 数据回流复盘 Agent 写入
   │ 可观测:   SQLite job_events + FastAPI SSE 实时 trace 控制台
```

### 2.1 角色（Agent 架构对应 JD 常见措辞）

| 角色 | 模块 | 类型 | 职责 |
|---|---|---|---|
| Analyst | `analyst.py` | 分工型 | 视频 → 结构化"爆款DNA"(钩子/结构/语气/人群) |
| Writer | `writer.py` | 分工型 | DNA+经验库 → 原创脚本(标题/封面/4-6段口播/简介) |
| Reviewer | `reviewer.py` | **评审型** | 规则硬检 + LLM 打分，不过打回并给修改意见 |
| Producer | `media.py`/`tools/tts.py` | 执行型 | CosyVoice 逐段配音 + PIL 卡片 + ffmpeg 出片 |
| Publisher | `loop.py` | 人机协同 | 产出发布包，人工投稿后回填 BVID（human-in-the-loop）|
| Replier | `replier.py` | **复盘型** | 数据 → 经验教训 → 写入经验库 |
| Metrics | `metrics.py`+`scheduler.py` | 后台 | 定时拉取公开数据，驱动复盘 |

---

## 3. 技术栈与选型

- 编排：**LangGraph**（StateGraph/条件边/循环/`SqliteSaver` checkpoint）
- LLM/Embedding/ASR/TTS：SiliconFlow 统一 OpenAI 兼容网关
  - 结构化 JSON 任务默认 `deepseek-ai/DeepSeek-V3`（实测 Qwen2.5-7B 不遵循 JSON schema）
  - Embedding `BAAI/bge-m3`；ASR `FunAudioLLM/SenseVoiceSmall`；TTS `FunAudioLLM/CosyVoice2-0.5B`
- 数据源：B站真实公开接口；抖音/快手/小红书分享链接 best-effort 解析 + 手动回退
- 出片：Pexels/本地授权素材 + Pillow 字幕卡 + CosyVoice TTS + ffmpeg
- 可选生成：图片默认关闭远程优先，视频生成默认关闭；需要时再手动开启 `GENERATION_FIRST` / `VIDEO_GENERATION_ENABLED`
- 存储：SQLite（任务/事件/指标/经验库）+ LangGraph checkpoint SQLite
- 服务：FastAPI + SSE 实时 trace 控制台（原生 HTML/JS，零前端依赖）
- 调度：APScheduler（默认关闭，环境变量开启）

---

## 4. 快速开始

```powershell
# 0) conda 环境（python 3.12）与依赖
conda create -n contentforge python=3.12 -y
conda activate contentforge
pip install -r requirements.txt
# 额外：LangGraph SQLite checkpoint
pip install langgraph-checkpoint-sqlite aiosqlite

# 1) 配 key（SiliconFlow：https://cloud.siliconflow.cn/account/ak）
copy .env.example .env                     # 填 SILICONFLOW_API_KEY
# 可选：填 PEXELS_API_KEY；SiliconFlow 用于 AI 图片/视频生成
# AI 生成模型可用 .env 覆盖：IMAGE_MODEL、IMAGE_FALLBACK_MODEL、VIDEO_MODEL

# 可选：准备本地授权素材和背景音乐目录
mkdir data/assets, data/music -Force

# 2) 启动控制台
$env:PYTHONIOENCODING='utf-8'
python -m uvicorn forge.server.app:app --port 8017
# 浏览器打开 http://127.0.0.1:8017

# 3) 命令行单条生产（不渲染只看脚本用 --no-render）
python -m forge.pipeline --bvid BV1wFZ8YBEt4
python -m scripts.run_job --bvid BV1wFZ8YBEt4
# 只有审核通过后的内容才建议显式出片
python -m forge.pipeline --bvid BV1wFZ8YBEt4 --render
```

### 闭环演示路径（控制台 UI）

1. 新建任务：贴链接或完整分享文案 → 生成事实摘要、3 个角度、脚本和分镜。
2. 检查 `content_assets.md`；通过、打回或编辑后重新审核。
3. 审核通过后按需生成视频，再进入发布回填。
4. 同步数据后进入复盘经验库。

---

## 5. API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/jobs` | 创建生产任务（body: `source`,`style`,`channel`,`target_platforms`,`manual?`）|
| GET | `/api/jobs` | 任务列表 |
| GET | `/api/jobs/{id}` | 任务详情 |
| GET | `/api/jobs/{id}/assets` | 返回内容资产包 |
| GET | `/api/jobs/{id}/events` | **SSE** 实时/回放事件流（`?last=事件id`）|
| POST | `/api/jobs/{id}/review` | 审核：`approve/reject/edit` |
| POST | `/api/jobs/{id}/render` | 审核通过后手动触发视频渲染 |
| POST | `/api/jobs/{id}/publish` | 标记已发布（body: `bvid`），并触发首次回流+复盘 |
| POST | `/api/jobs/{id}/sync` | 同步数据 + 复盘 |
| GET | `/api/jobs/{id}/metrics` | 数据指标快照 |
| GET | `/api/experience` | 经验库（`?q=` 语义搜索 / 空=全量）|
| GET | `/api/generation/capabilities` | 当前图片/视频生成能力 |
| POST | `/api/sources/import` | 批量导入多平台分享链接（解析失败进入人工补录）|
| GET | `/api/sources/trending` | B站榜单；其他平台返回已导入队列 |
| POST | `/api/jobs/{id}/publish/prepare` | 生成各平台发布包 |
| POST | `/api/jobs/{id}/publish/mark` | 记录某平台人工发布 ID/链接 |
| POST | `/api/jobs/{id}/metrics/import` | 手动导入某平台指标并进入复盘 |

## 5.1 MCP / Agent 工具接入

项目提供 MCP server，可以让 Claude Code / Codex / opencode 等编码 Agent 直接调用内容工厂：

```powershell
python -m forge.mcp_server
```

暴露工具：`list_jobs`、`get_job`、`create_job`、`get_job_trace`、
`search_experience`、`eval_runs`。这是“让 AI 工具编排 AI 应用”的演示入口，
也是 JD 中 MCP / Tool Use 的直接可讲案例。

## 5.2 离线评测

不依赖 LLM 和 B站，只审计本地产物：

```powershell
$env:PYTHONIOENCODING='utf-8'
python -m forge.evalkit --json
```

统计：规则合规通过率、Review 通过率、人工复核率、中位段数、单段字数、
经验引用数、Top 规则失败原因。作为 Agent 工作流的回归信号，而不是“感觉效果不错”。

---

## 6. 目录结构

```
forge/
├─ config.py / llm.py / store.py / scheduler.py
├─ channels/             # B站真实适配器 + 抖音/快手/小红书分享页适配器
├─ transcript.py          # 文案提取链：CC字幕 → 音频ASR(SenseVoice)
├─ analyst.py / writer.py / reviewer.py / replier.py
├─ assets.py              # Pexels + 本地素材，缓存与指纹去重
├─ video_manifest.py      # 分镜 manifest + SRT 字幕时间轴
├─ asset_pack.py          # 内容资产包 JSON + Markdown 导出
├─ job_flow.py            # 人工审核、编辑和打回重写
├─ media.py               # 可选成片：授权素材/卡片 + TTS + ffmpeg
├─ publish.py             # 多平台发布包与人机协同发布记录
├─ tools/asr.py tools/tts.py
├─ experience.py          # 向量经验库（embedding + 余弦召回）
├─ metrics.py / loop.py   # 数据回流与闭环服务
├─ graph.py               # LangGraph 组装 + checkpoint + 运行入口
├─ agents/nodes.py        # LangGraph 节点实现（发事件/落盘）
└─ server/app.py + static # FastAPI + SSE 控制台
scripts/                  # 命令行与批量工具（pipeline/render_existing/run_job/batch_produce）
tests/                    # pytest（67 用例）
```

---

## 7. 工程要点（面试可展开）

1. **多智能体编排**：分工/评审/复盘三种协作模式；条件边实现"审稿不过→带 feedback 打回 Writer"，最多 2 次，耗尽后生成带人工复核标记的资产包。
2. **两级记忆**：短期 = LangGraph `SqliteSaver` checkpoint（thread_id=job_id，可续跑/可回溯状态）；长期 = 向量经验库，数据回流复盘后写入，Writer 检索注入 prompt → 形成**自优化闭环**。
3. **工具可靠性与幻觉缓解**：空来源禁止创作、主题一致性和事实支撑硬检、结构化输出容错、LLM 调用重试和明确错误提示。
4. **可观测性**：SQLite `job_events` + SSE 控制台逐事件回放；checkpoint 可查状态。
5. **工程化**：pytest(67)、Docker 化友好、`requirements.txt`、配置与环境分离。
6. **合规/风控意识**：采集只读匿名低频，不保存 Cookie、不模拟登录；平台风控页不绕过；发布走人工确认并记录发布 ID。

---

## 8. 用 AI Coding 以 SDD 方式开发（开发日志）

本项目用 Claude Code 风格的智能体以 **Spec-Driven Development** 开发：

1. **Spec**：先写 `PROJECT_CONTEXT.md`(决策/范围/DoD) 与 `引导.md`(架构/命令/校验清单)，固化后再动代码。
2. **环境先行**：新建 conda `contentforge`(py3.12)，一次性装依赖，ffmpeg 用 imageio-ffmpeg 内置。
3. **垂直切片优先**：先打通最险的外链（B站采集→ASR→LLM改写→出片），再上编排框架，风险前置。
4. **小步验证**：每步用真实接口探针验证（榜单/音频流/ASR/CosyVoice），发现即修：
   - Qwen2.5-7B 不遵循 JSON schema → 结构化任务切 DeepSeek-V3
   - edge-tts 域名被墙 → 换 SiliconFlow CosyVoice（voice 带模型前缀）
   - 榜单普遍无 CC 字幕 → 音频流 + ASR 兜底
   - conda run 的 GBK stdout 崩 → 脚本只打 ASCII，结果落 JSON
5. **测试后置补强**：对外部依赖用探针、对纯逻辑用 pytest(67) 锁定。
6. **文档同步**：README/引导/决策记录与代码同步更新，防偏移。

---

## 9. 测试

```bash
python -m pytest -q   # 67 passed（规划/资产包/审核/分镜/素材/发布/分享文本）
```

## 10. 已知边界与后续

- 抖音/快手/小红书无官方开放权限时采用分享页 best-effort 解析，失败必须手动补录；不绕过验证码。
- 发布仍是**人机协同**，官方 API 发布留作后续适配器扩展。
- 复盘数据为公开指标或人工导入，未做完播率等站内埋点数据。
- 默认交付内容资产包，视频渲染是审核通过后的可选步骤。
- 渲染优先本地素材、授权素材和图文卡；AI 视频默认关闭，图片生成可按环境配置启用。
- v1 不实现真实口型驱动和多角色连续剧情。
- 后续可加：多 BVID 队列并行、失败自动重试与告警、经验库淘汰、Dify/低代码对比层。
