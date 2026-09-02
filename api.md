# 急诊绿通进出记录接口（摘自接口文档）

## 患者查询全量合并流转数据

- 方法: `GET`
- 路径: `/emergency/rfidInOutArea/getInOutMergeList`
- Header: `Authorization: Bearer {token}`
- Header: `buildId` 楼栋/院区 ID（number）

### 请求参数

| 位置 | 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| Query | hospitalNo | string | 与 epc 至少其一 | 门诊号/住院号，如 MZ20260608001 |
| Query | epc | string | 与 hospitalNo 至少其一 | 腕带 EPC，如 E200001234560001 |
| Query | startTime | string | 与 endTime 成对 | `YYYY-MM-DD HH:MM:SS` |
| Query | endTime | string | 与 startTime 成对 | `YYYY-MM-DD HH:MM:SS` |

业务规则：

- `hospitalNo` 和 `epc` 至少一个，否则返回空数组
- `startTime` 和 `endTime` 必须同时传入才过滤时间

### 返回 data[] 字段

| 字段 | 说明 |
|------|------|
| type | 1 进 / 2 出 / 3 抵达 / 4 业务操作 / 5 进出事件 |
| type2 | type=5 时：1 进 / 2 出 / 3 抵达 |
| wristbandEpc | 手环编号 |
| areaName | 区域 |
| importName | 进出口 |
| importName2 | type 为 4 或 5 时的节点名 |
| createTime | 时间 |
| patientName | 患者姓名 |
| hospitalNo | 门诊号/住院号 |
