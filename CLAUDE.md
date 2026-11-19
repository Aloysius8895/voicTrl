# 工作规则

## 先用 general 技能

每个任务开工前，先从 `general/skills/skills/` 选出对口的技能，读它的 `SKILL.md` 并照做。这些技能没有注册到 Skill 工具，"调用技能"就是读文件照做。

1. **选技能**：按下表对号；表里没有的情况，读路由 `general/skills/skills/engineering/ask-matt/SKILL.md` 再选。
2. **读全文**：读所选技能的 `SKILL.md` 和它指向的同目录文件。技能里写 "call the Skill tool with X" 时，改读 `general/skills/skills/*/X/SKILL.md`。
3. **报一声**：动手前用一行告诉用户在用哪个技能；确实没有对口的，说出原因再做。

完成标准：开始做任务本身之前，已经说出所用技能，或没有对口技能的理由。

| 情况 | 技能 |
|---|---|
| 查资料、核实文档或 API | `engineering/research` |
| 打磨想法、方案、设计 | `productivity/grilling`（在仓库里用 `engineering/grill-with-docs`） |
| 用一次性代码回答设计问题 | `engineering/prototype` |
| 写功能、修 bug | `engineering/tdd` |
| 难缠的 bug、性能变慢 | `engineering/diagnosing-bugs` |
| 审代码 | `engineering/code-review` |
| 写 PR 描述 | `engineering/pr` |
| 只有人能做的步骤（开账号、配密钥、点第三方后台） | `engineering/wizard` |
| 写或改 CLAUDE.md、AGENTS.md、技能 | `productivity/writing-for-agents` |
| 一个会话装不下的大计划 | `engineering/wayfinder` |

## 用户触发的技能

frontmatter 含 `disable-model-invocation: true` 的技能（wayfinder、grill-with-docs、to-spec、to-tickets、implement 等）由用户启动：判断对口时用一行建议，用户同意后再跑。

## 范围

默认只用 `engineering/` 和 `productivity/`；`in-progress/`、`misc/`、`deprecated/` 在用户点名时才用。

## 已知缺口

`setup-matt-pocock-skills` 尚未运行，没有配置 issue tracker。用到 tracker 的技能（to-tickets、wayfinder、triage）开始前，先问用户 tracker 放在哪里。
