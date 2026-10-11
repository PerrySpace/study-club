# 更新日志

本项目的所有重要变更都会记录在此文件。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循[语义化版本（Semantic Versioning）](https://semver.org/lang/zh-CN/)。

> ⚠️ 当前为**初始版本（v0.1）**，尚未打首个正式 tag。

## [Unreleased]

### 进行中

- 内容扩容进行中（字库、古诗、短文与故事）。

## [0.1.0]

第一版可运行（first runnable release）。

### Added

- **Web PWA 三档响应式**（手机 / iPad / 桌面）：学习地图、字卡、闯关、每日任务、复习、错题本、古诗、故事、学情报告、设置。
- **邀请码身份与准入**：邀请码 + 自设口令，支持 `REQUIRE_INVITE` 开关（默认免码开放，设为 `true` 强制校验）。
- **云端后台**：内容 / 身份 / 儿童档案 / 学习与复习 / 报告 / 匿名统计 / 反馈 / 素材托管 / 可选加密同步。
- **单管理员内容后台**。
- **内容即仓库**：`content/**/*.json` + JSON Schema + 校验脚本。
- **四份 Docker Compose 分服务独立编排**（`deploy/mongo`、`deploy/api`、`deploy/web`、`deploy/admin`）与 `scripts/` 运维脚本。
