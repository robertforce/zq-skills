---
name: spec-compliance-check
description: Use when 完成代码实现后，在代码审查之前，检查实现是否符合OpenSpec规范
---

# 规范合规审查

## 铁律
任何实现必须与 openspec/specs/ 中的规范一致。不一致就是bug。

## 审查步骤

1. 读取 openspec/specs/ 下的主规范（检查本次实现是否违反了已有需求）
2. 读取本次变更对应的 openspec/changes/ 下的 delta 规范
3. 逐条检查每个"假设/当/则"场景是否有对应实现
4. 检查 design.md 中提到的架构决策是否被遵守
5. 检查 proposal.md 的排除范围是否被违反

## 常见问题

- "AI顺手多改了代码"：检查排除范围
- "实现方式和 design.md 不一致"：这是 bug，不是优化
- "场景没有覆盖"：测试不完整