# scripts/seed —— 种子数据与内容导入

按「一张表/一个功能一个文件」组织，文件名前缀决定导入顺序。导入器幂等（用 `unique_key` upsert）。

## 用法

```bash
scripts/seed/seed.sh                      # 按文件名顺序导入全部
scripts/seed/seed.sh --only characters    # 只导入文件名包含 characters 的表
scripts/seed/seed.sh --only 04_char       # 也可用前缀
scripts/seed/seed.sh --drop               # 导入前清空各目标集合（谨慎）
scripts/seed/seed.sh --mongo-uri mongodb://localhost:27017/study_club
```

> `seed.sh` **优先在 api 容器内执行**（依赖与路径都已就绪），容器未运行时才退回本机 `python3`。
> 因此 `deploy/api/docker-compose.yml` 把 `scripts/seed/data` 与 `content` **只读挂载**进容器
> —— 这样新签发的邀请码 JSON、或新加的一张种子表，**不需要重建镜像**就能被导入。
> 若不使用容器，需本机 `python3` 能导入 `motor`（导入器在 `apps/api` 内）。

## 文件格式

每个 `data/*.json` 是一个「规格」，两种写法：

**① 直导（自己写文档）**

```json
{
  "collection": "invites",
  "feature": "邀请码",
  "unique_key": "code_hash",
  "documents": [ { "code_hash": "…", "code_hint": "…", "batch_id": "…" } ]
}
```

**② 从内容包导入**

```json
{
  "collection": "characters",
  "feature": "汉字主表",
  "source": "content/characters/grade-1.json",
  "strip_wrapper": true,
  "unique_key": "_id"
}
```

- `source` 相对**仓库根**；内容包形如 `{content_version, items:[…]}`，用 `strip_wrapper: true` 取 `items`。
- 单文档（如清单）：用 `single_doc_id` 指定 `_id`。
- 若文档自带 `_id`，则优先按 `_id` upsert（内容包天然如此）。

## 怎么加一张新表的种子数据

1. 在 `data/` 新建文件，例如 `11_child_badges.json`，按上面任一格式写好。
2. 字段名必须与 [docs/03-数据设计/02-数据字典.md](../../docs/03-数据设计/02-数据字典.md) 逐字一致（snake_case）。
3. 指定 `unique_key`（无则退化为按 `_id`，再退化则仅插入，不幂等）。
4. 执行 `scripts/seed/seed.sh --only 11_child_badges` 验证；确认后再跑全量。
5. 若该表有对应集合，确认其索引已写入 `apps/api/app/db/mongo.py` 的索引清单。

## 只用某一张表

```bash
scripts/seed/seed.sh --only poems      # 导入 05_poems.json
scripts/seed/seed.sh --only assets     # 导入 09_assets.json
```

`--only` 做的是「文件名包含匹配」，因此 `--only 04` 或 `--only characters` 都行。

## 纪律

- **邀请码种子只放哈希**，不放明文码；明文码用 `scripts/api/issue-invites.sh` 现场签发并只输出一次。
  签发产物 `invites-*.csv`（明文）与 `invites-*.json`（哈希）均已 `.gitignore`，**不入库** ——
  需要导入时在本机/服务器上现场签发 + `scripts/seed/seed.sh --only invites` 即可。
  ⚠️ `01_invites.json` 里的「示例批次」是**演示数据，其明文码不存在**，无法用于注册；
  要测试注册请先签发真码（见 `scripts/api/README` 或根 README 快速开始）。
- **账号种子不放明文口令**：`passcode_hash` 留空（不可登录），或用 `scripts/api/hash-password.sh` 生成后填入；
  也可在**本地副本**里写 `passcode` 字段，导入器会哈希后入库且不留明文。
- 内容变更的主路径是改 `content/` 里的 JSON（Git 版本管理），本目录只负责「把内容推进数据库」。
