# Security and Privacy

CodexJobAgent 可能处理简历、岗位记录和招聘沟通，因此隐私问题应视为安全问题。

## 不要在公开 Issue 中提交

- 真实姓名与联系方式组合；
- 完整简历；
- 身份证件或银行卡信息；
- 密码、验证码、Cookie、Token、API Key；
- 招聘平台登录状态；
- 包含私人聊天或账号信息的截图、录屏；
- `.local/`、运行数据库或审计日志。

## 本地检查

发布前运行：

```powershell
python scripts/privacy_audit.py
```

也建议检查：

```powershell
git status
git diff --cached
```

如果发现已经把密钥或个人数据提交到 Git 历史中，仅删除当前文件通常不够；应立即撤销/轮换相关凭据，并清理 Git 历史后再发布。
