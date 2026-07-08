---
name: openspec-superpowers-bridge
description: Use when 开始实现 OpenSpec 的 tasks，在 brainstorming 和 planning 之前自动加载。当用户说"开始实现"、"apply tasks"或提到 OpenSpec 变更时触发
---

# OpenSpec-Superpowers衔接规范

## 铁律
实现任何OpenSpec task之前，必须先加载对应的规范文档。没有规范上下文的实现就是盲写代码。

## 执行步骤

1. 读取 openspec/specs/ 下的主规范（了解已有约束）和 openspec/changes/ 下最新的未归档变更目录中的所有文档（如果不确定当前变更目录，运行 `ls openspec/changes/` 查看未归档的变更文件夹。如果只有一个，那就是当前变更。如果有多个，询问用户确认）
2. 如果 OpenSpec 的 explore 和 propose 已经完成，跳过 Superpowers 的 brainstorming 阶段，直接进入 planning 阶段
3. 把 design.md 作为 Superpowers planning 的输入
4. 把 specs/ 中的场景转换为 TDD 测试用例
5. 把 tasks.md 中的每个任务拆成 Superpowers plan 的粒度
6. 每个任务完成后，用 spec-compliance-check 审查规范合规
7. 全部任务完成后，运行 /opsx:verify
8. verify 通过后，运行 Superpowers verification（跑测试命令）
9. 两个验证都通过，才能 /opsx:archive

## 场景到测试的转换规则

OpenSpec 的"假设/当/则"场景映射为测试用例，每个场景至少需要两个测试：

1. 正常路径测试：假设对应 setup，当对应 action，则对应 assertion
2. 错误路径测试：假设对应异常条件，当对应 action，则对应错误 assertion
3. 边界值测试：如果场景涉及数值、时间等边界，额外添加

## 审查的双重检查

每次代码审查必须包含两个维度：
1. 代码质量（Superpowers默认审查）
2. 规范合规（spec-compliance-check Skill）

## 常见问题

- "AI 没读 design.md 就实现了"：检查衔接 Skill 是否触发
- "tasks 粒度太粗"：自动拆成TDD步骤
- "verify 通过了但测试没跑"：archive 前强制跑测试