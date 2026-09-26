# CodexJobAgent

CodexJobAgent 是一个面向个人求职场景的本地辅助框架，用于组织从候选人资料、岗位发现、JD 标准化、去重与匹配，到候选池生成和人工复核的完整流程。

项目强调 **local-first、privacy-aware、human-in-the-loop**：个人资料和运行数据默认保存在本地，高影响操作由用户确认，不绕过登录、验证码或平台风控。

## Features

- 候选人资料初始化与本地隔离管理
- 多候选人配置支持
- 公开岗位数据标准化
- 岗位指纹生成与保守去重
- JD 与候选人能力匹配
- 岗位来源质量评估
- 岗位发现计划与搜索反馈记录
- 薪资信息标准化
- 候选池生成与优先级排序
- SQLite 本地数据存储
- 投递过程审计记录
- 发布前隐私扫描
- 可选 Android MCP 辅助操作
- 基础单元测试

## Workflow

```text
Candidate Profile
      │
      ▼
Public Job Sources
      │
      ▼
Job Discovery
      │
      ▼
Normalization
      │
      ▼
Deduplication
      │
      ▼
Matching & Eligibility Check
      │
      ▼
Candidate Pool
      │
      ▼
Human Review
      │
      └── Optional Assisted Application
```

候选池中的岗位仅表示“推荐进一步查看”，不代表已经投递。

## Project Structure

```text
CodexJobAgent/
├─ config/        公共配置与评分策略
├─ examples/      合成候选人和岗位示例
├─ onboarding/    候选人资料初始化说明
├─ scripts/       核心处理脚本
├─ skills/        Codex 项目技能说明
├─ templates/     本地配置模板
├─ tests/         基础单元测试
├─ third_party/   可选第三方组件
├─ AGENTS.md      项目级 Agent 规则
├─ START_HERE.md  首次使用入口
└─ requirements.txt
```

真实个人资料、运行数据库和审计数据不应提交到公开仓库。

## Requirements

推荐环境：

- Windows 10 / 11
- Python 3.12+
- PowerShell
- Codex 或能够读取项目级 `AGENTS.md` 的兼容环境

安装 Python 依赖：

```powershell
python -m pip install -r requirements.txt
```

## Quick Start

### 1. 获取项目

下载仓库 ZIP 并解压，或使用 Git：

```powershell
git clone <repository-url>
cd CodexJobAgent
```

### 2. 初始化环境

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1
```

初始化脚本会创建 Python 环境、安装依赖，并生成本地配置骨架。

正常完成后应看到：

```text
BOOTSTRAP_OK
```

### 3. 初始化候选人资料

阅读：

```text
START_HERE.md
```

按照引导提供简历或候选人信息。

只有经过用户确认的事实才应写入本地候选人配置。

完成后运行：

```powershell
.\.venv\Scripts\python.exe scripts\validate_profile.py
```

正常结果：

```text
PROFILE_OK
```

## Synthetic Examples

仓库中的 `examples/` 仅包含合成数据，可用于了解数据结构和测试核心功能。

例如：

```text
examples/profile_demo/
examples/jds/
examples/discovery_strategy/
```

这些文件不包含真实候选人资料，也不应修改为真实个人信息后提交到公开仓库。

## Job Processing

典型岗位处理流程包括：

```text
Job discovery
→ normalization
→ deduplication
→ matching
→ candidate pool
```

核心脚本包括：

| Script | Purpose |
|---|---|
| `job_discovery.py` | 标准化公开岗位记录 |
| `job_deduplicator.py` | 岗位去重 |
| `job_matcher.py` | JD 与候选人匹配 |
| `candidate_pool.py` | 生成候选池 |
| `salary_normalizer.py` | 薪资标准化 |
| `source_quality.py` | 岗位来源质量评估 |
| `init_db.py` | 初始化本地数据库 |
| `privacy_audit.py` | 隐私检查 |

部分候选人可使用独立 matcher 和 scoring 配置，实现不同候选人之间的数据、策略和评分隔离。

## Multi-Candidate Support

CodexJobAgent 支持多个候选人使用同一套代码。

公共仓库只保存：

```text
candidate_a
candidate_b
```

这类匿名候选人标识和通用配置。

真实姓名、联系方式、毕业信息、简历事实和求职偏好应保存在本地私人配置中，而不是写入公共源码。

这样可以让：

```text
Shared code
     │
     ├── Candidate A private profile
     └── Candidate B private profile
```

共享同一套工作流，同时保持个人数据相互隔离。

## Local Database

项目可以使用 SQLite 保存：

- 岗位记录
- 岗位指纹
- 匹配结果
- 候选池状态
- 操作审计记录

初始化：

```powershell
.\.venv\Scripts\python.exe scripts\init_db.py
```

运行数据库属于本地数据，不应提交到公共仓库。

## Privacy

项目设计原则是：

> Source code can be public; personal job-search data should remain local.

公开仓库中不应保存：

- 真实简历
- 姓名和联系方式
- 身份证件信息
- 登录密码
- Cookie
- Access Token
- Refresh Token
- API Key
- 私钥
- 验证码
- 本地数据库
- 真实招聘聊天记录

发布前建议运行：

```powershell
python scripts/privacy_audit.py
```

正常结果：

```text
PRIVACY_AUDIT_OK
```

也可以附加自定义禁止词：

```powershell
python scripts/privacy_audit.py ^
  --forbidden-term "Your Name" ^
  --forbidden-term "Private Identifier"
```

隐私扫描只能作为辅助检查，公开代码前仍建议进行人工复核。

## Human-in-the-Loop

项目不会把“发现岗位”或“加入候选池”等同于真实投递。

以下操作应由用户确认：

- 提交真实申请
- 发送招聘消息
- 确认薪资
- 确认面试时间
- 确认入职日期
- 接受 Offer
- 修改关键个人资料

登录、验证码、滑块、人机验证及平台风险控制应始终由用户本人处理。

## Optional Android MCP

`third_party/mobile-use-mcp/` 提供可选 Android 辅助能力，可用于经过人工确认的移动端操作流程。

它不是核心岗位匹配功能的必要依赖。

启用相关功能前应确保：

- Android SDK `adb` 可用
- 设备已开启 USB 调试
- 用户已经完成登录
- 验证码和风控步骤由用户本人处理

第三方代码继续遵循其目录中附带的 LICENSE 和 NOTICE。

## Testing

运行测试：

```powershell
python -m unittest discover -s tests
```

检查 Python 文件：

```powershell
python -m compileall scripts
```

执行隐私审计：

```powershell
python scripts/privacy_audit.py
```

推荐在修改匹配、发现、评分或候选人隔离逻辑后重新运行上述检查。

## Limitations

CodexJobAgent 是一个可配置的本地求职辅助框架，而不是通用招聘推荐模型。

实际使用效果仍受到以下因素影响：

- 岗位数据质量
- 页面更新和岗位失效
- 不同招聘平台的数据结构差异
- 候选人资料完整度
- 匹配规则与评分配置
- 招聘平台 UI 和风控策略变化

因此最终岗位选择和申请决策仍应由用户本人完成。

## Disclaimer

本项目用于辅助整理、筛选和管理公开招聘信息。

使用者应遵守目标网站和招聘平台的服务条款、访问规则及当地适用法律，不应使用本项目绕过身份验证、访问控制或平台安全机制。
