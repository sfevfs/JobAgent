# Contributing

感谢对 CodexJobAgent 的改进。这个项目处理求职资料和平台操作，因此修改时应优先保证事实约束、隐私和可审计性。

## 提交前

```powershell
python -m pip install -r requirements.txt
python -m compileall scripts
python scripts/privacy_audit.py
```

至少使用 `examples/jds/` 和合成 profile 做一次离线回归检查。

## 修改原则

- 不提交真实简历、真实招聘聊天、截图、数据库或运行日志。
- 新增示例必须明确标记为 synthetic / 合成数据。
- 不把未知候选人字段自动填成真实值。
- 不新增绕过登录、验证码、限流或平台风控的逻辑。
- 涉及真实提交动作时，应保留人工确认和审计记录。
- 修改 matcher 权重或关键词时，应说明预期影响并提供最小验证样例。
- 修改 `third_party/` 时必须保留原许可证和归属信息。

## Pull Request 建议内容

PR 描述应包含：

- 修改目的；
- 影响的脚本或配置；
- 使用的合成测试数据；
- 运行过的验证命令；
- 是否改变真实投递、通信或手机操作边界。
