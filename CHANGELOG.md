# 更新日志

本项目的所有重要变更都会记录在此文件。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循[语义化版本（Semantic Versioning）](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added

- **后台内容物理删除**：内容删除接口 `DELETE /admin/content/{collection}/{id}` 新增 `hard`、`force` 两个查询参数。`hard=true` 时先检查引用（关卡 / 单元 / 短文），仍被引用则拒绝并回传引用明细（错误码 `40903 CONTENT_IN_USE`），确认要删可用 `force=true` 强制。**默认行为不变**，仍为「下架」（仅置 `status → offline`）。
- **学习伙伴**：新增 `apps/web/src/composables/useCompanion.ts` 作为头像与称呼的唯一来源；关卡、引导气泡、朗读按钮、设置页统一跟随孩子所选头像显示，不再各自写死「小兔」。
- **内容字段以 schema 为唯一真源**：`scripts/content/validate.mjs` 改为读取 `content/schema/*.json` 校验字段形状（必填齐备 + 无未声明字段），不再在脚本里手抄一份字段清单。
- **关卡完成页四条出口**：再练一次 / 下一关 / 换线闯关 / 回地图（「回地图」常驻，不再只在末关出现）。
- **文档站**：补充 `robots.txt` 与 Open Graph / Twitter 社交分享卡片 meta。
- **seed**：新增 `--force` 逃生舱，用于显式声明「以仓库内容为准」。

### Changed

- **关卡生成改为按内容「自身年级」分桶**（前端 `packages/core/src/algorithms/lessons.ts` 与后端 `apps/api/app/seed/lesson_generator.py` 逐条对齐）：
  - `target_grade` 语义由「单一年级」改为**年级上限**，缺省不限（取 `GRADE_MAX`）；
  - 学龄前（`grade = 0`）内容不再被并入一年级；学龄前孩子现在能看到 0 年级关卡。
- **seed 内容优先级**：镜像型集合（`characters` / `poems` / `stories` / `readings` / `curriculum_units` / `badges`）在**集合为空**时以仓库内容初始化；**库中已有数据时以库为准**（只补缺，不覆盖同名文档、不删除库内独有文档）。`lessons` 属派生型，始终重算并清理失效文档。
- **管理端年级清单**改为跟随站点配置派生（后端把年级扩到 7/8/9 时无需改前端），并补上「故事」内容页。
- **文档站**：仓库外链统一指向 Gitee 主仓库，填入 GitHub 镜像地址；补充文档站开发说明（跨平台构建注意事项）。

### Fixed

- 修复学龄前内容「能导入却看不见」：`grade = 0` 曾在 `item.get("grade") or 1` 中被当作 falsy 静默升为一年级。
- 修复发布流程会物理删除后台导入内容：曾两次在部署时清空运营导入的 3509 个汉字 + 141 首古诗（seed 日志 `stale_removed`），且 `content_version` 被打回仓库基线。
- 修复 `content/schema/character.schema.json` 漏声明 `glyph` 字段，导致按 schema 生成的导入模板对现有字库**全部不通过**。
- 修复内容字段文档中 `pictograph`（实为字形说明**文字**）与 `glyph`（字源**图**）的语义混淆；`glyph` 补入字符 schema 必填项。
- **CI / 文档站构建**：Windows 平台原生依赖（`@esbuild/win32-x64`、`@rollup/rollup-win32-x64-msvc`）由 `dependencies` 移入 `optionalDependencies`，修复 Linux runner 的 `EBADPLATFORM`；CI 安装前丢弃跨平台 `package-lock.json` 重装，修复 `@rollup/rollup-linux-x64-gnu` 缺失；Node 运行时升到 22。

### Documentation

- 更新 `scripts/seed/README.md`、`deploy/api/README.md`：记录内容优先级规则与年级语义。
- 修正 `docs/06-工程规范/01-开发规范与前端架构.md` 分支模型表中的生产分支（`main` → `master`）。

## [0.1.0] - 2026-10-11

第一版可运行（first runnable release）。

### Added

- **Web PWA 三档响应式**（手机 / iPad / 桌面）：学习地图、字卡、闯关、每日任务、复习、错题本、古诗、故事、学情报告、设置。
- **邀请码身份与准入**：邀请码 + 自设口令，支持 `REQUIRE_INVITE` 开关（默认免码开放，设为 `true` 强制校验）。
- **云端后台**：内容 / 身份 / 儿童档案 / 学习与复习 / 报告 / 匿名统计 / 反馈 / 素材托管 / 可选加密同步。
- **单管理员内容后台**。
- **内容即仓库**：`content/**/*.json` + JSON Schema + 校验脚本。
- **四份 Docker Compose 分服务独立编排**（`deploy/mongo`、`deploy/api`、`deploy/web`、`deploy/admin`）与 `scripts/` 运维脚本。

[Unreleased]: https://github.com/PerrySpace/study-club/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/PerrySpace/study-club/releases/tag/v0.1.0
