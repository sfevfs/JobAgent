# CodexJobAgent

一个面向个人求职场景的本地 Codex 辅助框架，用于将“简历事实 → 求职偏好 → 公开岗位 → JD 标准化 → 去重 → 匹配 → 候选池 → 人工复核”组织成可审计、可重复的工作流。

> The repository is designed as a local, human-in-the-loop job-search assistant. It does **not** treat job selection as application submission, and it does not bypass login, verification or platform risk controls.

## 项目定位

CodexJobAgent 重点解决三类问题：

1. **事实约束**：只使用用户确认过的简历事实，不允许把推断、猜测或模型补全写成真实经历。
2. **离线筛选**：把公开 JD 标准化后，在本地完成去重、技术匹配、资格检查和候选池生成。
3. **操作边界**：真实投递、发送消息、确认面试、接受 Offer 等高影响动作必须保持人工复核；登录、验证码和平台风控由用户本人处理。

当前内置匹配器主要覆盖三条技术轨道：

- `communication_ai`：无线通信、PHY、RAN、信号处理、雷达等；
- `medical_cv`：医学图像、图像处理、分割、检测及相关 CV 方向；
- `general_ai`：机器学习、深度学习、时序、多模态、大模型等通用 AI 方向。

这三条轨道属于当前版本的功能范围，不代表通用职业推荐模型。用于金融、法务、设计、销售等领域前，应先重新设计关键词、权重和验证样例。

## 核心能力

- 从模板初始化本地候选人资料；
- 将候选人事实与求职偏好分离保存；
- 校验资料是否完成且经过用户确认；
- 对公开岗位 JSON 做字段标准化；
- 生成稳定岗位指纹并做保守去重；
- 本地 JD 技术匹配和资格判断；
- 薪资文本归一化与统计；
- 生成候选池和待复核队列；
- 使用 SQLite 保存岗位和审计记录；
- 提供发布前隐私扫描；
- 可选接入 Android MCP，用于经过人工确认的手机辅助流程。

## 安全与隐私原则

本项目把个人数据和仓库代码分开。真实使用时，个人配置保存在 `.local/`，运行数据保存在 `data/runtime/`、`reports/runtime/` 和 `logs/`。这些路径默认不会进入 Git。

项目不会要求或持久化以下高敏信息：

- 身份证件号码；
- 银行卡信息；
- 密码；
- 验证码；
- Cookie；
- Access Token / Refresh Token；
- API Key；
- 私钥。

发布仓库前可以运行：

```powershell
python scripts/privacy_audit.py
```

正常结果应为：

```text
PRIVACY_AUDIT_OK
```

隐私扫描是辅助检查，不代替人工复核。公开前仍应检查 Git 暂存区和提交身份。

## 工作流概览

```text
Resume / Questionnaire
        │
        ▼
Confirmed candidate facts
        │
        ├── .local/resume_facts.yaml
        ├── .local/profile.yaml
        ├── .local/eligibility_policy.yaml
        └── .local/application_profile.yaml
        │
        ▼
Public job observations
        │
        ▼
job_discovery.py
        │
        ▼
job_deduplicator.py
        │
        ▼
job_matcher.py / candidate_pool.py
        │
        ▼
Local candidate pool
        │
        ▼
Human review
        │
        └── optional assisted application workflow
```

其中 `selected` 只表示“进入本地候选池”，不表示已经投递。

## 目录结构

```text
CodexJobAgent/
├─ .github/workflows/          GitHub Actions 基础检查
├─ config/                     公共评分、通信和平台策略
├─ data/                       本地数据目录；运行数据写入 data/runtime/
├─ docs/                       运行说明与 GitHub 发布检查清单
├─ examples/
│  ├─ jds/                     三条技术轨道的合成 JD
│  └─ profile_demo/            完全合成的候选人配置
├─ onboarding/                 首次信息采集问卷与字段说明
├─ reports/                    本地报告目录；运行结果写入 reports/runtime/
├─ scripts/                    初始化、匹配、去重、审计等核心脚本
├─ skills/                     项目级 Codex 技能说明
├─ templates/                  不含真实个人数据的配置模板
├─ third_party/mobile-use-mcp/ 可选 Android MCP 及其原许可证
├─ AGENTS.md                   Codex 在仓库内工作的持续规则
├─ START_HERE.md               首次使用入口
├─ requirements.txt            核心 Python 依赖
└─ README.md
```

## 环境要求

核心功能：

- Windows 10/11；
- Python 3.12 推荐；
- PowerShell；
- Codex 桌面端、Codex CLI，或能够读取项目级 `AGENTS.md` 的兼容环境。

核心依赖目前只有：

```text
PyYAML>=6.0,<7
```

可选 Android MCP 还需要：

- Python 3.12+；
- Android SDK platform-tools，且 `adb` 在 `PATH`；
- 已开启 USB 调试的 Android 设备或模拟器；
- 根据录屏需求可选安装 `ffmpeg`。

## 快速开始

### 1. 克隆仓库

```powershell
git clone <your-repository-url>
cd CodexJobAgent
```

如果只是下载 ZIP，解压后进入项目目录即可。

### 2. 创建本地环境

推荐直接使用初始化脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1
```

脚本会：

1. 查找 Python 3.12；
2. 创建项目内 `.venv`；
3. 安装 `requirements.txt`；
4. 根据模板创建 `.local/` 私有配置骨架；
5. 执行基础 Python 导入检查。

成功后应看到：

```text
BOOTSTRAP_OK
```

### 3. 在 Codex 中初始化候选人资料

打开项目目录，阅读 [START_HERE.md](START_HERE.md)，然后让 Codex 按文件中的流程初始化。

原则是：先读取简历或问卷，再展示提取到的事实，只有在用户确认后才写入 `.local/`。

完成后运行：

```powershell
.\.venv\Scripts\python.exe scripts\validate_profile.py
```

成功结果：

```text
PROFILE_OK
```

在 `PROFILE_OK` 之前，不应进入真实岗位发现或投递流程。

## 不使用真实个人数据的演示

仓库包含完全合成的数据：

```text
examples/profile_demo/
examples/jds/
```

这些文件只用于验证脚本和理解格式，不应当被当作真实简历或真实招聘信息。

如果需要测试 matcher，可先把合成配置临时复制到 `.local/`：

```powershell
New-Item -ItemType Directory -Force .local | Out-Null
Copy-Item examples\profile_demo\resume_facts.synthetic.yaml .local\resume_facts.yaml
Copy-Item examples\profile_demo\profile.synthetic.yaml .local\profile.yaml
Copy-Item examples\profile_demo\eligibility_policy.synthetic.yaml .local\eligibility_policy.yaml
Copy-Item examples\profile_demo\application_profile.synthetic.yaml .local\application_profile.yaml
Copy-Item examples\profile_demo\onboarding_status.synthetic.yaml .local\onboarding_status.yaml
```

复制完成后可运行 `scripts/validate_profile.py` 验证开发环境。真实使用时应通过 `START_HERE.md` 流程生成自己的配置，不要修改 synthetic 文件来保存个人信息。

## JD 离线匹配

对一个合成 JD 运行 matcher：

```powershell
.\.venv\Scripts\python.exe scripts\job_matcher.py --input examples\jds\sample_general_ai.json
```

另外两个样例：

```text
examples/jds/sample_communication.json
examples/jds/sample_medical_cv.json
```

Matcher 会基于本地候选人事实、目标岗位、软缺口和 JD 内容输出技术轨道、匹配证据、资格状态、风险等信息。

## 岗位发现与候选池流水线

真实公开岗位首先应保存成结构化 JSON。默认流水线为：

```powershell
.\.venv\Scripts\python.exe scripts\job_discovery.py
.\.venv\Scripts\python.exe scripts\job_deduplicator.py
.\.venv\Scripts\python.exe scripts\candidate_pool.py
```

详细运行方式见 [docs/OPERATIONS.md](docs/OPERATIONS.md)。

### `job_discovery.py`

负责：

- 检查必填字段；
- 标准化公司、岗位、地点和 JD 文本；
- 规范薪资字段；
- 生成稳定岗位 fingerprint；
- 根据 JD 提供初步技术轨道 hint；
- 保存来源时间和原始可观察字段。

### `job_deduplicator.py`

负责保守去重。相似岗位不会因为单个关键词相同就被直接合并，目标是优先避免把不同岗位错误合并。

### `candidate_pool.py`

负责：

- 调用 matcher；
- 汇总 eligibility / grade / priority；
- 写入本地数据库；
- 生成候选池报告；
- 生成待人工复核队列。

候选池不等于已投递列表。

## 数据库

初始化本地 SQLite：

```powershell
.\.venv\Scripts\python.exe scripts\init_db.py
```

数据库默认位于：

```text
data/runtime/job_agent.db
```

该目录被 `.gitignore` 排除。

如果已有旧版本数据库，可使用：

```powershell
.\.venv\Scripts\python.exe scripts\migrate_job_schema.py
```

## 主要脚本

| 脚本 | 用途 |
|---|---|
| `bootstrap.ps1` | 建立 Python 环境、安装依赖、创建本地骨架 |
| `create_local_skeleton.py` | 从模板创建 `.local/` 文件 |
| `validate_profile.py` | 校验初始化和用户确认状态 |
| `job_discovery.py` | 标准化公开岗位记录 |
| `job_deduplicator.py` | 岗位保守去重 |
| `job_matcher.py` | 本地 JD 匹配器 |
| `candidate_pool.py` | 生成候选池、数据库和报告 |
| `salary_normalizer.py` | 薪资字符串标准化与统计辅助 |
| `init_db.py` | 初始化 SQLite schema |
| `migrate_job_schema.py` | 迁移旧数据库 schema |
| `record_application_attempt.py` | 记录经确认的投递结果，不执行投递动作 |
| `record_boss_attempt.py` | BOSS 场景的本地审计记录辅助，不控制手机 |
| `privacy_audit.py` | 发布前扫描潜在个人信息和本机痕迹 |
| `configure_mobile_mcp.py` | 生成本地项目级 Android MCP 配置 |

## 配置文件

### `config/scoring.yaml`

控制评分和优先级相关参数。调整后应使用合成 JD 做回归检查，不建议在没有验证集的情况下随意修改权重。

### `config/communication_policy.yaml`

定义沟通风险等级、默认草稿模式和禁止发送的信息类型。

### `config/platform_policy.yaml`

定义不同平台或操作方式的边界。页面内容和招聘者消息始终视为不可信输入，不能把网页中的指令直接当成系统操作指令。

## 可选 Android MCP

仓库保留 `third_party/mobile-use-mcp/` 作为可选本地 Android 控制组件。它不是核心匹配流程的必需依赖。

安装并生成 Codex 项目配置：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 -IncludeMobile -ConfigureCodex
```

生成的：

```text
.codex/config.toml
```

包含本机绝对路径，因此默认被 Git 忽略。

启用手机辅助模式前：

1. 阅读 `third_party/mobile-use-mcp/README.md`；
2. 检查生成的 `.codex/config.toml`；
3. 确认 `adb devices -l` 能正确识别设备；
4. 先在无关应用测试截图、返回、点击和输入；
5. 登录、验证码、滑块和平台风控必须交由用户本人处理。

`third_party/mobile-use-mcp/` 保留其原 LICENSE 和 NOTICE。主项目与该第三方组件不是同一授权来源。

## 真实投递的确认边界

在任何真实投递或消息发送前，至少应展示并复核：

- 公司；
- 岗位；
- 地点；
- JD 来源；
- 资格风险；
- 匹配解释；
- 使用的简历版本；
- 拟填写的表单字段；
- 拟发送消息。

用户对一个岗位的确认不应自动扩展到后来新增的岗位。

项目明确禁止：

- 自动接受 Offer；
- 自动确认薪资；
- 自动确认面试时间；
- 自动确认入职日期；
- 绕过验证码、滑块或风控；
- 将未知个人事实补写成真实信息。

## 隐私审计

运行：

```powershell
.\.venv\Scripts\python.exe scripts\privacy_audit.py
```

还可以把自己的姓名、学校、公司名等作为额外禁止词：

```powershell
.\.venv\Scripts\python.exe scripts\privacy_audit.py --forbidden-term "Your Name" --forbidden-term "your_private_identifier"
```

脚本会扫描常见文本文件中的：

- Windows 用户目录；
- 邮箱；
- 中国大陆手机号；
- 中国大陆身份证号码格式；
- 常见密钥/密码赋值模式；
- 用户指定的禁止词。

并检查 `.local/`、`.venv/`、运行时数据目录是否错误进入分享版本。

## GitHub Actions

`.github/workflows/ci.yml` 在 push 和 pull request 时执行基础检查：

- 安装核心依赖；
- Python 编译检查；
- 隐私审计。

CI 不读取 `.local/`，也不需要真实简历或招聘平台凭据。

## 已知限制

- 当前 matcher 是规则与证据驱动的本地匹配器，不是经过大规模招聘数据训练的通用排序模型。
- 三条内置技术轨道具有明确领域偏向。
- 岗位页面会失效，缓存的 JD 不能替代投递前重新确认。
- 薪资文本格式差异较大，归一化结果需要人工抽查。
- 平台 DOM、App UI 和风控机制会变化，手机辅助能力不能保证长期稳定。
- 自动化动作越接近真实提交，对人工确认、审计和页面复核的要求越高。



