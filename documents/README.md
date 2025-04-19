# py-xiaozhi 文档

这是 py-xiaozhi 项目的文档网站，基于 VitePress 构建。

## 功能

- 项目指南：提供项目的详细使用说明和开发文档
- 赞助商页面：展示并感谢项目的所有赞助者
- 贡献指南：说明如何为项目贡献代码
- 贡献者名单：展示所有为项目做出贡献的开发者
- 响应式设计：适配桌面和移动设备

## 本地开发

```bash
# 安装依赖
pnpm install

# 启动开发服务器
pnpm docs:dev

# 构建静态文件
pnpm docs:build

# 预览构建结果
pnpm docs:preview
```

## 目录结构

```
documents/
├── docs/                  # 文档源文件
│   ├── .vitepress/        # VitePress 配置
│   ├── guide/             # 指南文档
│   ├── sponsors/          # 赞助商页面
│   ├── contributing.md    # 贡献指南
│   ├── contributors.md    # 贡献者名单
│   └── index.md           # 首页
├── package.json           # 项目配置
└── README.md              # 项目说明
```

## 赞助商页面

赞助商页面通过以下方式实现：

1. `/sponsors/` 目录包含了赞助商相关的内容
2. `data.json` 文件存储赞助商数据
3. 使用 Vue 组件在客户端动态渲染赞助商列表
4. 提供成为赞助者的详细说明和支付方式

## 贡献指南

贡献指南页面提供了以下内容：

1. 开发环境准备指南
2. 代码贡献流程说明
3. 编码规范和提交规范
4. Pull Request 创建和审核流程
5. 文档贡献指南

## 贡献者名单

贡献者名单页面展示了所有为项目做出贡献的开发者，包括：

1. 核心开发团队成员
2. 代码贡献者
3. 文档贡献者
4. 测试和反馈提供者

## 部署

文档网站通过 GitHub Actions 自动部署到 GitHub Pages。 