# 生成日系萌系女孩 Codex 宠物

## 目标

生成一只 Codex 兼容的自定义宠物，主题为“日系萌系女孩”，输出完整动画 spritesheet 与 `pet.json` 包装文件。

## 风格要求

- 整体为日系萌系二次元女孩风格
- 宠物安全风格，适合缩小到 `192x208` 单格阅读
- 统一脸型、发型、配色、服饰轮廓与材质
- 不包含文字、UI、logo、复杂背景

## 产物

- 1 个基础形象
- 9 个状态行：`idle`、`running-right`、`running-left`、`waving`、`jumping`、`failed`、`waiting`、`running`、`review`
- 最终 `spritesheet.webp`
- 对应 `pet.json`

## 验收标准

- 通过 hatch-pet 的 atlas 生成与校验流程
- 接触表与预览动画可读
- 所有状态保持同一角色身份与风格一致
- 输出位于 `${CODEX_HOME:-$HOME/.codex}/pets/<pet-id>/`
