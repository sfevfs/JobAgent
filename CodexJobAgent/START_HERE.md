# 从这里开始

首次使用 CodexJobAgent 时，用 Codex 打开仓库根目录，然后发送：

> 请按照 START_HERE.md 初始化这个求职项目。先检查依赖，然后请我上传或粘贴简历；只使用我确认过的事实建立本地配置。配置完成后先做公开岗位发现和离线匹配，不要直接投递或发送招聘消息。

推荐顺序：

1. 运行 `scripts/bootstrap.ps1` 建立 `.venv` 和 `.local/` 骨架；
2. 让用户上传或粘贴简历；
3. 从简历提取候选人事实；
4. 把“已确认 / 有歧义 / 缺失且影响求职”的字段展示给用户；
5. 每轮最多询问 5 个高影响问题；
6. 用户确认事实摘要后再写入 `.local/`；
7. 运行 `scripts/validate_profile.py`；
8. 只有得到 `PROFILE_OK` 后，才进入公开岗位发现和匹配阶段。

如果用户没有现成简历：

> 我没有可上传的简历，请按 onboarding/QUESTIONNAIRE.md 分轮问我，每轮最多 5 个问题。

初始化完成的校验命令：

```powershell
.\.venv\Scripts\python.exe scripts\validate_profile.py
```

成功结果：

```text
PROFILE_OK
```

注意：

- 不要把未知事实补写成真实经历；
- 不要要求身份证、银行卡、密码、验证码、Token 或 Cookie；
- `.local/` 是私人数据目录，不应提交 Git；
- `selected` 只代表进入本地候选池；
- 真实投递和真实消息必须经过针对具体岗位或明确批次的人工确认。
