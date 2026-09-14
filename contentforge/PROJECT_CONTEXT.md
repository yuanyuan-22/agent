# ContentForge 内容工厂 — 项目决策与上下文记录

> 目的：固化本次对话的所有分析结论与范围决策，**防止后期实现偏移**。
> 每次开工前先读本文件；范围变更必须先改这里再动代码。
> 最后更新：2026-09-10

---

## 1. 一句话定位

**多智能体内容策划与分镜 Agent**：从「源链接/完整文案 → 事实摘要 → 原创选题 → 脚本 → 分镜 → 审核 → 内容资产包」的工作流，用 LangGraph 编排。视频渲染是审核通过后的可选能力，不作为核心质量承诺。

## 2. 求职背景与目标（为什么要做这个）

- 学历：成都信息工程大学，人工智能本科，2026 届（已毕业，正在投 AI 应用开发方向）。
- 已有资产（可复用）：
  - 医疗毕设：LoRA 微调 + RAG(BGE-M3/FAISS/Qwen2.5) + ReAct 式 Function-Calling Agent + 评测(Recall/MRR/NDCG + LLM-as-Judge) + Django/DRF + Docker。
  - 有 SiliconFlow / DeepSeek API key；本地部署过大模型经验；有微信小号（不用于本项目）。
- 目标岗位画像：**通用 Agent 应用开发岗 15-30k**。JD 高频词：LangGraph/LlamaIndex/AutoGen、Function Calling/Tool Use、MCP、记忆(短期/长期)、多智能体(分工/评审/复盘)、RAG 进阶、评测与可观测、AI Coding(SDD/Harness/Skill)。
- 时间极紧：约 2 周出可演示成果。

## 3. 已确认的硬决策（不要悄悄改）

1. 旗舰项目 = **多智能体内容策划与分镜 Agent**。默认交付内容资产包，不做全自动视频生成承诺。
2. **渠道策略**：B站真实公开接口；抖音/快手/小红书支持分享链接 best-effort 解析与手动回退，不保存 Cookie、不模拟登录。
3. 默认交付 = `asset_pack.json + content_assets.md`。审核通过后可选渲染，优先本地素材/授权素材/图文卡，AI 视频默认关闭。
4. **发布走人机协同半自动**：系统生成多平台发布包，人工上传后回填视频 ID/链接；未来获得官方开放平台权限时替换为 API 发布。
5. **数据回流分层**：B站自动拉公开 stat；抖音/快手/小红书支持手动导入指标。所有指标进入同一复盘经验库。
6. **本地电脑运行**（不要求公网服务器部署）。每日定时任务默认关闭/低频，主要手动触发 + 演示时开一次。
7. LLM / Embedding / TTS 都走 **SiliconFlow**（OpenAI 兼容）。结构化 JSON 任务默认 `deepseek-ai/DeepSeek-V3`（实测 Qwen2.5-7B-Instruct 不遵循 JSON schema、产出退化内容，已不作默认）；Embedding `BAAI/bge-m3`；ASR `FunAudioLLM/SenseVoiceSmall`。
8. 依赖环境用 **conda 新建环境 `contentforge`（python 3.12）**，不动现有 envs。
9. 外部链条全部用免费/已有资源：B站公开接口 + edge-tts(免费) + imageio-ffmpeg(自带二进制) + 已有 API key。

## 4. 系统蓝图（LangGraph 主流程，一次生产任务）

```
选题(TrendAgent) → 拆解(AnalystAgent: 取字幕/简介→结构化"爆款DNA")
   → 改写(WriterAgent: 结合经验库记忆→新脚本+封面字)
   → 审稿(ReviewerAgent: 规则+LLM打分 → 不合格打回 Writer, 最多重试2次)   # reflection
   → 生成(ProducerAgent: edge-tts配音 + PIL图文卡片 + ffmpeg成片)          # tool use
   → 发布(PublisherAgent: 产出发布包) ──人工投稿+回填bvid──▶               # human-in-the-loop
   → 数据回流(MetricsJob 定时拉stat) → 复盘(ReplierAgent: 写经验→向量经验库)
   → 每日复盘报告(可选企微/钉钉机器人)
```

记忆设计：
- 短期 = LangGraph checkpointer（任务状态可查/可续跑）
- 长期 = 向量「经验库」（SQLite 存 embedding，余弦召回，供 Writer/选题参考）

Agent 架构对应 JD 措辞：分工型(选题/拆解/改写/生成/发布) + 评审型(Reviewer) + 复盘型(Replier)。

## 5. 仓库结构

```
contentforge/
├─ agents/           # LangGraph 各角色节点 (trend/analyst/writer/reviewer/producer/publisher/replier)
├─ graph.py          # StateGraph + 条件边 + checkpoint
├─ channels/         # 渠道适配器: bilibili 真实 + 抖音/快手/小红书分享页
├─ tools/            # 工具抽象: 字幕提取/经验库检索/成片/发布包
├─ store/            # SQLite(SQLAlchemy) 模型 + 经验库(向量余弦召回)
├─ server/           # FastAPI 控制台 + SSE 实时 trace
├─ scheduler.py      # APScheduler: 定时回流/复盘(默认关)
├─ scripts/          # 垂直切片脚本 / 手动触发
├─ tests/            # pytest 纯逻辑
├─ config.yaml       # 模型/渠道/调度开关
└─ README.md         # 架构图 + SDD 开发记录
```

## 6. B站接入与文案提取策略（只读，规避风控）

- 榜单/热门：`x/web-interface/ranking/v2`（`data.list`）、`x/web-interface/popular`（带 UA；必要时先访问 `www.bilibili.com` 拿 buvid3 cookie，处理 -412）。
- 详情：`x/web-interface/view?bvid=` → title/desc/tags/stat/cid。
- **文案提取链（transcript）**：CC 字幕（`x/player/v2`）优先；绝大多数榜单视频无 CC → 退化为**匿名下载音频流**（`x/player/playurl` fnval=16 有 dash.audio，实测匿名 code=0）→ ffmpeg 截取前 N 秒并转 16k 单声道 wav → SiliconFlow `FunAudioLLM/SenseVoiceSmall` ASR 转写。mode 记录来源(cc/asr/none)。
- 数据回流：`x/web-interface/view` 的 stat（公开，无需登录，取自己已发布视频）。
- 不攻坚上传反爬（见决策 4）。

## 7. 两周节奏（D1 当天起）

- D1-3 垂直切片：输入一个 B站爆款 URL → 拆解 → 改写 → 出 mp4（先不引 LangGraph，打通外部链路）
- D4-7 LangGraph 多智能体图 + Reviewer 打回重试 + checkpoint + SQLite 状态机 + FastAPI/SSE trace 页
- D8-10 Publisher 发布包 + 定时回流 + Replier 经验库 + 指标曲线 + 复盘报告
- D11-12 健壮性(重试/幂等/兜底) + pytest + 本地真实跑 3-5 条验证闭环
- D13-14 README(架构图 + SDD 记录) + 演示录屏 + 简历 bullet + 面试问答清单

## 8. 完成判据（Definition of Done）

1. 一次任务自动产出 mp4 + 封面 + 标题/简介/标签发布包；控制台可看完整多 Agent trace。
2. 至少 3 条视频真实发布到 B站，数据回流自动画出播放/互动曲线，复盘经验写入经验库且能被下次改写检索引用。
3. pytest 关键逻辑通过；README 含架构图与 AI Coding/SDD 过程；简历可写第 9 节 bullet。

## 9. 目标简历 bullets（对齐 15-30k Agent 岗）

1. 用 LangGraph 编排 6+ 类角色多智能体（分工/评审/复盘型），Reflection 打回重试 + human-in-the-loop 发布，任务状态可观测。
2. 短期(checkpoint)+长期(向量经验库)两级记忆；数据回流后复盘 Agent 沉淀经验→下次改写自动引用，形成自动优化闭环（播放/互动曲线可截图）。
3. 统一 Tool 抽象（字幕提取/经验库检索/ffmpeg 出片/发布包），结构化输出 + 参数校验防工具误调。
4. SSE 实时 trace、定时任务、幂等重试；关键逻辑 pytest。
5. README 记录以 Claude Code/opencode 的 Spec-Driven 方式开发全过程（对应 JD 的 AI Coding/SDD/Harness）。

## 10. 需要补齐的概念（面试高频，边做边学）

LangGraph(State/Node/条件边/checkpoint/多Agent supervisor)、Function Calling 与 JSON 结构化输出、工具参数校验与幻觉缓解、记忆分层与召回/遗忘、Reflection/自评循环、LLM-as-Judge 评测与 trace、SSE 流式、后台任务与幂等、平台风控与合规意识。

## 11. 风险与默认应答口径（面试准备）

- 版权/内容合规：只采集公开数据用于自有账号试验；改写出新文案、不直接搬运成片；答辩口径=「自有账号内容生产自动化」。
- 平台风控：不自动上传、控制采集频率、带 UA/尊重接口频率 → 展示工程与合规意识而非打擦边球。
- 反爬失效应对：channel 适配器接口化，B站被封可换视频号/手动清单数据源。

## 12. 开发现状（2026-09-13，内容资产包链路完成）

**环境**：conda env `contentforge` @ `F:\Anaconda3\envs\contentforge`（python 3.12.14），ffmpeg 用 imageio-ffmpeg 内置二进制。运行命令（在 `F:\agent\contentforge` 下）：
```
& F:\Anaconda3\envs\contentforge\python.exe -m forge.pipeline --bvid BVxxxx [--auto] [--no-render] [--style "..."]
& F:\Anaconda3\envs\contentforge\python.exe -m scripts.render_existing --script runs/<id>/script.json
```

**已完成**：
- LangGraph StateGraph / 条件打回 / SqliteSaver checkpoint / SSE trace 控制台均可用。
- 主流程默认停在 `awaiting_review`，产出 JSON + Markdown 内容资产包，不自动渲染。
- 人工审核支持通过、打回重写、编辑后再审；仅审核通过后可手动渲染。
- 四平台来源适配层：B站真实抓取；抖音/快手/小红书分享链接解析和人工回退。
- 素材层：Pexels + 本地素材选择、缓存、指纹去重；视频 manifest、SRT 字幕时间轴。
- V3 内容链路：InsightAgent → IdeationAgent → ScriptAgent → DirectorAgent。
- AI 生成层：Qwen-Image → Z-Image-Turbo → Pexels/本地/卡片降级；
  Wan2.2-I2V 关键镜头生成，失败回退关键帧动效。
- 固定虚拟讲解员：角色资产缓存、绿色背景抠图、场景叠加。
- 多平台发布包、发布记录和指标导入接口可用。
- `python -m forge.evalkit --json`、`python -m forge.mcp_server` 可用。
- `pytest` 67 用例全绿。

**实测要点**：JSON 类 LLM 任务必须用 DeepSeek-V3；stdout 中文需要 `PYTHONIOENCODING=utf-8`；
TTS mp3 有缓存；外部 B站链路仍只读、匿名、低频，发布走人工。
