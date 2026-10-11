# 贡献指南

> 站点版入口。**完整指南见仓库根 [CONTRIBUTING.md](https://gitee.com/perry-space/study-club/blob/master/CONTRIBUTING.md)（Gitee）** —— 细节、分支模型、提交规范都以它为准。

欢迎为**学习俱乐部（study-club）** 出力。它既是一个真正给孩子用的产品，也是一个**适合练手的开源项目**：无论你想写代码、补内容、改文档，还是先学学开源协作怎么运转，这里都欢迎你。

## 一、你可以贡献什么

| 类型 | 一句话说明 |
| --- | --- |
| **代码** | 修 bug、加功能、优化性能与可访问性；前端（Vue 3）与后端（Python 3.12 + FastAPI）都欢迎 |
| **内容** | 只改 `content/**/*.json` 即可：字条、古诗、短文、故事、徽章等，**不需要懂 Vue** |
| **文档** | 修正错漏、补充示例、把设计讲得更清楚 |
| **测试** | 补单元测试、端到端用例、边界场景 |
| **翻译** | 把界面与文档做成多语言（当前以中文为主） |
| **Issue** | 报 bug、提建议、反馈错别字或读音问题 |
| **Review** | 评审他人的 PR、复现问题、帮忙把关内容质量 |

> 从找一个 `good first issue` 开始，走完 fork → 改 → PR → 评审 → 合并的完整流程。

## 二、本地环境

| 前置 | 要求 |
| --- | --- |
| **Node** | ≥ 20 |
| **pnpm** | 9.12.0（仓库已固定 `packageManager`，建议用 Corepack 启用） |
| **Python** | 3.12 |
| **Docker** | Docker + Docker Compose（本地起 MongoDB / API 时用） |

常用命令：

```bash
pnpm install            # 安装依赖（首次需联网）
pnpm dev                # 学生端 / 家长端 Web（Vite dev server）
pnpm dev:admin          # 单管理员内容后台
pnpm typecheck          # 全仓类型检查
pnpm content:validate   # 校验 content/** 的 JSON 与 Schema
```

> 只想改内容？改 `content/**/*.json` + 跑 `pnpm content:validate` 即可，**不需要跑起整个应用**。

## 三、四条红线

1. **密钥不进仓库**：仓库里只有 `.env.example`。
2. **不改内容版权红线**：不携带教材映射、不收录来源不明的素材。
3. **掩藏能力保持关闭**：需企业主体的能力（手机号 / 微信、支付、小程序、App）**默认关闭、不打包、不部署**；**多角色 RBAC 后台同属本期不做**（单管理员足够，与企业主体无关）。
4. **兼容性只增不改不删**：接口字段 / 枚举只增；破坏性变更走 `/api/v2`。

## 四、用 AI，但要对结果负责

我们**鼓励**用 AI 工具（编码助手、翻译、内容草拟）来提效，但底线是：

> **你提交的每一行，都要自己看得懂、自己验证过、自己负责。**

提 PR 前自检：

- ✅ `pnpm -r typecheck` 通过（前端全仓类型检查为绿）；
- ✅ 相关功能**确实跑通**了（自己点一遍、跑一遍，别只看 AI 说「已完成」）；
- ✅ 内容改动跑过 `pnpm content:validate`，Schema 校验为绿；
- ⚠️ 如果你看不懂自己提交的代码，就不要提交。

## 继续阅读

- 完整贡献指南 → [CONTRIBUTING.md](https://gitee.com/perry-space/study-club/blob/master/CONTRIBUTING.md)
- 常见问题 → [常见问题](/docs/faq)
- 内容怎么改 → [内容体系与创作](/docs/content)
