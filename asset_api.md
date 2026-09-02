# 设备追踪与能效分析 — 智能体用到的查询接口

来源：设备追踪与能效分析 API V3.6。只接只读查询，不接新增/删除/编辑。

鉴权：`appid` + `buildId` + `signature`（参数排序后拼 secret，MD5 大写）。
前缀：`http://IP:8086`

| 用途 | 方法 | 路径 |
|------|------|------|
| 设备列表 | GET | `/goods` |
| 设备详情/实时位置 | GET | `/goods/{id}` |
| 能效分析列表 | GET | `/getEnergyEfficiencyPage` |
| 开关机记录 | GET | `/getOnOffRecord` |
| 轨迹摘要 | GET | `/userPaths` |
| 耗电统计 | GET | `/electricQuantity/list` |

关键枚举：

- `assetType`：0 能效 / 1 定位
- `communicateStatus`：0 离线 / 1 在线
- `alarmStatus`：`over_boundary` 越界 / `tamper` 防拆 / `off_line` 离线 / `low_power` 低电量
- `energyEfficiencyStatus`：0 关机 / 1 待机 / 2 运行 / 3 闲置
