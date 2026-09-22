# 术语表（Into the Radius 2 简体中文）

游戏：Into the Radius 2（半径之内 2）——VR 生存射击，背景为佩乔尔斯克陨石坑周边的「半径」隔离区。
中文译名沿用游戏标题《半径之内》。

## 固定译法

| 英文 | 中文 | 说明 |
| --- | --- | --- |
| Radius | 半径 | 区域名，不加「区域」二字；"Return to the Radius" → 返回半径 |
| Pechorsk | 佩乔尔斯克 | 地名 |
| Anomaly | 异常 | 复数为异常区/异常体时按上下文 |
| Anomaly cluster | 异常簇 | |
| Artifact / artefact | 神器 | 原作社区译法 |
| Mimic | 拟态怪 | 敌人名 |
| Fragment | 碎片 | e.g. Regeneration Fragment → 再生碎片 |
| Explorer | 探索者 | 玩家身份/等级 |
| Tide | 潮汐 | 事件名 |
| UNPSC | UNPSC | 不译，保留英文缩写 |
| Facility 27 | 27 号设施 | |
| Access Level | 权限等级 | |
| Security Level | 安全等级 | |
| Priority / TopPriority | 优先级 / 最高优先级 | 任务代号 |
| Forest Scout | 森林侦察 | 任务代号 |
| Changelog | 更新日志 | |
| Probe | 探针 | 探测异常用的小球 |
| Detector | 探测器 | 神器探测器 |
| Terminal | 终端 | |
| Stash | 藏匿点 | 地图上的藏身处 |
| Loot | 战利品 | |
| Backpack | 背包 | |
| Holster | 枪套 | |
| Pouch | 弹药袋 / 挎包 | 按上下文 |
| Save / Load | 存档 / 读档 | 名词；动词用保存/载入 |
| Slot | 槽位 | 存档槽位 → 存档栏位 |
| Ironman | 铁人 | 模式名 |
| Stamina | 体力 | 手表上的蓝条 |
| Health | 生命值 | |
| Weight | 负重 | |
| Condition | 耐久度 | 武器/装备状态 |
| Repair | 修理 | |
| Attachment | 配件 | 枪械配件 |
| Rail | 导轨 | |
| Dovetail mount | 燕尾槽导轨 | |
| Suppressor | 消音器 | |
| Magazine | 弹匣 | |
| Ammo Box | 弹药盒 | |
| Tracer | 曳光弹 | |
| FMJ | FMJ | 保留（全金属被甲弹） |
| Anomaly protection | 异常防护 | |
| Settings | 设置 | |
| Measurement | 计量单位 | |
| Metric / Imperial | 公制 / 英制 | |
| On / Off | 开 / 关 | |
| Yes / No | 是 / 否 | |
| OK | 确定 | |
| Back | 返回 | |
| Cancel | 取消 | |
| Start new game | 开始新游戏 | |
| Tutorial | 教程 | |
| Missions / Quests | 任务 | |
| Main mission | 主线任务 | |
| Side mission | 支线任务 | |
| Objective | 目标 | |
| Marker | 标记 | |
| Subtitle | 字幕 | |

## 格式与占位符规则（必须严格遵守）

1. `{X}` 形式的占位符原样保留，不得翻译或删除，例如 `{Percent}`、`{NumLoaded}`、`{TotalToLoad}`、`{Value}`。
2. 富文本标签原样保留：`<b>…</b>`、`</>`、`<br>`、`<bold>…</>`、`<color=…>`。
3. 转义与换行原样保留：`\r\n`、`\n`、`\t`；原文首尾的空格/换行必须保留（例如 `" - untitled - "` 保留两端空格）。
4. `#BUTTON`、`%s`、`{}` 之类控制记号不译。
5. 纯数字、纯符号（`*`、`+`、`(0/99)`、`+12h`、`...`）原样输出。
6. 武器型号、口径、缩写（AKM、M4、PM、TT、9x18、.338、UNPSC、EFOS、NATO）保留原样。
7. 语气：UI 与按钮用简短名词或动宾短语（不超过 10 个汉字优先）；任务描述、笔记、字幕用自然书面语。
8. 不添加原文没有的标点；英文句末句号可保留为中文句号「。」，但按钮/标签类不加句号。
