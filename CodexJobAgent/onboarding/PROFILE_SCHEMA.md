# 私有配置字段约定

个人配置保存在 `.local/`，由 Codex 根据用户确认的事实创建。可从 `templates/` 复制骨架，但不能把示例占位符当成事实。

## resume_facts.yaml

- `metadata.onboarding_complete` 必须为 `true`。
- `candidate` 保存学历、专业、毕业时间和求职状态。
- `education`、`employment`、`internships`、`projects`、`publications`、`competitions`、`certifications` 分开记录。
- `skills.catalog` 用统一技能名记录等级与证据。
- `projects.<id>.keywords` 保存可与 JD 比较的短语；必须来自已确认项目内容。
- `forbidden_claims` 保存不能声称的内容。

## profile.yaml

- `target_roles` 是岗位名列表，可按 P0/P1/P2 分组。
- `location`、`job_search`、`company_preferences`、`salary` 都是偏好，不得覆盖资格判断。
- `soft_gap.engineering` 只表示需要人工复核，不自动构成拒绝。
- 内置三轨匹配器仍使用 `communication_ai`、`medical_cv`、`general_ai`。若职业方向不同，需要先改造匹配器和验证数据。

## eligibility_policy.yaml

只记录硬资格与不确定边界。资格与技术分必须分开：学历或毕业届次不符可以导致 `ineligible`，但不能伪造或反向修改技术能力分。

