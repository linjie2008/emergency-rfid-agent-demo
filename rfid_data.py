"""急诊绿通 RFID 进出记录 — 与接口文档字段对齐的 mock 数据。"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any

TYPE_IN = 1
TYPE_OUT = 2
TYPE_ARRIVE = 3
TYPE_BIZ = 4
TYPE_IO = 5

TYPE_LABEL = {1: "进", 2: "出", 3: "抵达", 4: "业务操作", 5: "进出事件"}
TYPE2_LABEL = {1: "进", 2: "出", 3: "抵达"}

GATES = {
    "分诊台": ("分诊台入口", "分诊台出口"),
    "抢救室": ("抢救室入口", "抢救室出口"),
    "CT室": ("CT入口", "CT出口"),
    "DR室": ("DR入口", "DR出口"),
    "介入室": ("介入室入口", "介入室出口"),
    "卒中单元": ("卒中单元入口", "卒中单元出口"),
    "观察室": ("观察室入口", "观察室出口"),
    "手术室": ("手术室入口", "手术室出口"),
    "检验科": ("检验入口", "检验出口"),
    "CCU": ("CCU入口", "CCU出口"),
    "ICU": ("ICU入口", "ICU出口"),
    "产科": ("产房入口", "产房出口"),
    "儿科急诊": ("儿科入口", "儿科出口"),
    "收费处": ("大厅入口", "大厅出口"),
    "病房": ("病房入口", "病房出口"),
}


def _event(
    *,
    t: datetime,
    patient: str,
    hospital_no: str,
    epc: str,
    area: str,
    gate: str,
    kind: int,
    node: str | None = None,
    type2: int | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "type": kind,
        "wristbandEpc": epc,
        "areaName": area,
        "importName": gate,
        "createTime": t.strftime("%Y-%m-%d %H:%M:%S"),
        "relatedEpc": None,
        "patientName": patient,
        "hospitalNo": hospital_no,
    }
    if node:
        row["importName2"] = node
    if type2 is not None:
        row["type2"] = type2
    return row


def _io(t, patient, no, epc, area, gate, type2, node) -> dict[str, Any]:
    return _event(
        t=t,
        patient=patient,
        hospital_no=no,
        epc=epc,
        area=area,
        gate=gate,
        kind=TYPE_IO,
        node=node,
        type2=type2,
    )


def _biz(t, patient, no, epc, area, gate, node) -> dict[str, Any]:
    return _event(
        t=t,
        patient=patient,
        hospital_no=no,
        epc=epc,
        area=area,
        gate=gate,
        kind=TYPE_BIZ,
        node=node,
    )


def _ids(seq: int, prefix: str = "MZ20260608", epc_prefix: str = "E20000123456") -> tuple[str, str]:
    return f"{prefix}{seq:03d}", f"{epc_prefix}{seq:04d}"


def play_path(
    t0: datetime,
    name: str,
    hospital_no: str,
    epc: str,
    stops: list[tuple[str, int, list[str]]],
    still: bool = False,
) -> list[dict[str, Any]]:
    """按停留生成进出事件。still=True 表示仍留在最后一站。"""
    rec: list[dict[str, Any]] = []
    cur = t0
    for i, (area, minutes, nodes) in enumerate(stops):
        last = i == len(stops) - 1
        gate_in, gate_out = GATES.get(area, (f"{area}入口", f"{area}出口"))
        rec.append(_io(cur, name, hospital_no, epc, area, gate_in, 1, nodes[0] if nodes else f"进入{area}"))
        stay = max(minutes, 1)
        if nodes:
            gap = max(1, stay // (len(nodes) + 1))
            for j, node in enumerate(nodes, start=1):
                rec.append(
                    _biz(
                        cur + timedelta(minutes=min(stay - 1, gap * j)),
                        name,
                        hospital_no,
                        epc,
                        area,
                        area,
                        node,
                    )
                )
        leave = not (last and still)
        if leave:
            rec.append(
                _io(
                    cur + timedelta(minutes=stay),
                    name,
                    hospital_no,
                    epc,
                    area,
                    gate_out,
                    2,
                    f"离开{area}",
                )
            )
            cur = cur + timedelta(minutes=stay + 1)
    return rec


def infer_current_location(events: list[dict[str, Any]]) -> str:
    if not events:
        return "未知"
    events = sorted(events, key=lambda r: r["createTime"])
    open_areas: dict[str, str] = {}
    last = events[-1]
    for row in events:
        kind = row.get("type")
        action = TYPE2_LABEL.get(row.get("type2") or 0, "") if kind == 5 else TYPE_LABEL.get(kind or 0, "")
        area = row.get("areaName") or ""
        if action in ("进", "抵达") and area:
            for prev in list(open_areas):
                if prev != area:
                    open_areas.pop(prev, None)
            open_areas[area] = row["createTime"]
        elif action == "出" and area:
            open_areas.pop(area, None)
    if open_areas:
        return next(iter(open_areas))
    if (last.get("type") == 5 and last.get("type2") == 2) or last.get("type") == 2:
        return "已离开"
    return last.get("areaName") or "未知"


def _core_patients(now: datetime, today: datetime) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
    """保留原 5 个样例，Skill 测试依赖他们。"""
    records: list[dict[str, Any]] = []
    patients: dict[str, dict[str, str]] = {}

    def add(name, no, epc, channel, events):
        patients[no] = {"name": name, "epc": epc, "channel": channel, "day": "today"}
        records.extend(events)

    p, no, epc = "张三", "MZ20260608001", "E200001234560001"
    t0 = today.replace(hour=8, minute=12)
    add(
        p,
        no,
        epc,
        "胸痛绿通",
        [
            _io(t0, p, no, epc, "分诊台", "分诊台入口", 1, "到达分诊"),
            _biz(t0 + timedelta(minutes=2), p, no, epc, "分诊台", "分诊台", "分诊"),
            _io(t0 + timedelta(minutes=4), p, no, epc, "分诊台", "分诊台出口", 2, "离开分诊"),
            _io(t0 + timedelta(minutes=5), p, no, epc, "抢救室", "抢救室入口", 1, "进入抢救"),
            _biz(t0 + timedelta(minutes=8), p, no, epc, "抢救室", "抢救室", "心电图"),
            _biz(t0 + timedelta(minutes=12), p, no, epc, "抢救室", "抢救室", "抽血"),
            _io(t0 + timedelta(minutes=18), p, no, epc, "抢救室", "抢救室出口", 2, "离开抢救"),
            _io(t0 + timedelta(minutes=20), p, no, epc, "CT室", "CT入口", 1, "CT检查"),
            _io(t0 + timedelta(minutes=32), p, no, epc, "CT室", "CT出口", 2, "离开CT"),
            _io(t0 + timedelta(minutes=34), p, no, epc, "抢救室", "抢救室入口", 1, "返回抢救"),
            _io(t0 + timedelta(minutes=58), p, no, epc, "抢救室", "抢救室出口", 2, "离开抢救"),
            _io(t0 + timedelta(minutes=60), p, no, epc, "介入室", "介入室入口", 1, "介入治疗"),
        ],
    )

    p, no, epc = "李四", "MZ20260608002", "E200001234560002"
    t0 = today.replace(hour=7, minute=40)
    add(
        p,
        no,
        epc,
        "卒中绿通",
        play_path(
            t0,
            p,
            no,
            epc,
            [
                ("分诊台", 5, ["分诊"]),
                ("抢救室", 23, ["溶栓评估"]),
                ("CT室", 12, ["CT检查"]),
                ("抢救室", 43, ["溶栓"]),
                ("卒中单元", 1, ["收治住院"]),
            ],
            still=True,
        ),
    )

    p, no, epc = "王五", "MZ20260608003", "E200001234560003"
    t0 = today.replace(hour=6, minute=50)
    add(
        p,
        no,
        epc,
        "创伤绿通",
        [
            _io(t0, p, no, epc, "分诊台", "分诊台入口", 1, "到达分诊"),
            _biz(t0 + timedelta(minutes=4), p, no, epc, "分诊台", "分诊台", "分诊"),
            _io(t0 + timedelta(minutes=6), p, no, epc, "抢救室", "抢救室入口", 1, "进入抢救"),
            _biz(t0 + timedelta(minutes=20), p, no, epc, "抢救室", "抢救室", "清创"),
            _io(t0 + timedelta(minutes=55), p, no, epc, "DR室", "DR入口", 1, "拍片"),
            _io(t0 + timedelta(minutes=70), p, no, epc, "DR室", "DR出口", 2, "离开DR"),
            _io(t0 + timedelta(minutes=72), p, no, epc, "抢救室", "抢救室入口", 1, "返回抢救"),
        ],
    )

    p, no, epc = "赵六", "MZ20260608004", "E200001234560004"
    t0 = now - timedelta(minutes=8)
    add(
        p,
        no,
        epc,
        "急诊绿通",
        [
            _io(t0, p, no, epc, "分诊台", "分诊台入口", 1, "到达分诊"),
            _biz(t0 + timedelta(minutes=2), p, no, epc, "分诊台", "分诊台", "分诊"),
        ],
    )

    p, no, epc = "陈七", "MZ20260608005", "E200001234560005"
    t0 = today.replace(hour=9, minute=5)
    add(
        p,
        no,
        epc,
        "急诊绿通",
        [
            _io(t0, p, no, epc, "分诊台", "分诊台入口", 1, "到达分诊"),
            _biz(t0 + timedelta(minutes=3), p, no, epc, "分诊台", "分诊台", "分诊"),
            _io(t0 + timedelta(minutes=6), p, no, epc, "抢救室", "抢救室入口", 1, "进入抢救"),
            _io(t0 + timedelta(minutes=25), p, no, epc, "抢救室", "抢救室出口", 2, "离开抢救"),
            _io(t0 + timedelta(minutes=28), p, no, epc, "观察室", "观察室入口", 1, "留观"),
            _io(t0 + timedelta(minutes=95), p, no, epc, "观察室", "观察室出口", 2, "离开观察"),
            _io(t0 + timedelta(minutes=96), p, no, epc, "收费处", "大厅出口", 2, "离院"),
        ],
    )
    return records, patients


def _extra_today(today: datetime) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
    """当天扩容：多通道、多状态，方便问「CT室有谁 / 胸痛几人 / 还有谁超时」。"""
    specs: list[dict[str, Any]] = [
        # 胸痛
        {"name": "周杰", "seq": 6, "channel": "胸痛绿通", "h": 7, "m": 8, "still": True,
         "stops": [("分诊台", 4, ["分诊"]), ("抢救室", 15, ["心电图", "抽血"]), ("CT室", 14, ["CT检查"]),
                   ("抢救室", 18, ["会诊"]), ("介入室", 50, ["介入治疗"])]},
        {"name": "吴芳", "seq": 7, "channel": "胸痛绿通", "h": 9, "m": 40, "still": True,
         "stops": [("分诊台", 5, ["分诊"]), ("抢救室", 12, ["心电图"]), ("CT室", 20, ["CT检查"])]},
        {"name": "郑强", "seq": 8, "channel": "胸痛绿通", "h": 10, "m": 15, "still": True,
         "stops": [("分诊台", 3, ["分诊"]), ("抢救室", 22, ["心电图", "抽血"])]},
        {"name": "冯丽", "seq": 9, "channel": "胸痛绿通", "h": 6, "m": 20, "still": True,
         "stops": [("分诊台", 4, ["分诊"]), ("抢救室", 18, ["心电图"]), ("CT室", 11, ["CT检查"]),
                   ("介入室", 55, ["介入治疗"]), ("CCU", 8, ["收治住院"])]},
        {"name": "陈敏", "seq": 10, "channel": "胸痛绿通", "h": 8, "m": 50, "still": False,
         "stops": [("分诊台", 6, ["分诊"]), ("抢救室", 30, ["心电图", "会诊"]), ("观察室", 70, ["留观"]),
                   ("收费处", 2, ["离院"])]},
        {"name": "蒋涛", "seq": 11, "channel": "胸痛绿通", "h": 11, "m": 5, "still": True,
         "stops": [("分诊台", 4, ["分诊"]), ("抢救室", 10, ["心电图"]), ("检验科", 15, ["急查肌钙蛋白"])]},
        # 卒中
        {"name": "沈燕", "seq": 12, "channel": "卒中绿通", "h": 6, "m": 55, "still": True,
         "stops": [("分诊台", 3, ["分诊"]), ("抢救室", 12, ["溶栓评估"]), ("CT室", 15, ["CT检查"]),
                   ("抢救室", 25, ["溶栓"]), ("卒中单元", 20, ["收治住院"])]},
        {"name": "韩磊", "seq": 13, "channel": "卒中绿通", "h": 8, "m": 5, "still": True,
         "stops": [("分诊台", 4, ["分诊"]), ("抢救室", 20, ["溶栓评估"]), ("CT室", 13, ["CT检查"]),
                   ("抢救室", 35, ["溶栓"]), ("卒中单元", 10, ["收治住院"])]},
        {"name": "曹洋", "seq": 14, "channel": "卒中绿通", "h": 10, "m": 2, "still": True,
         "stops": [("分诊台", 5, ["分诊"]), ("抢救室", 8, ["溶栓评估"]), ("CT室", 18, ["CT检查"])]},
        {"name": "丁雪", "seq": 15, "channel": "卒中绿通", "h": 9, "m": 18, "still": True,
         "stops": [("分诊台", 4, ["分诊"]), ("抢救室", 40, ["溶栓评估", "会诊"])]},
        {"name": "潘伟", "seq": 16, "channel": "卒中绿通", "h": 7, "m": 22, "still": True,
         "stops": [("分诊台", 3, ["分诊"]), ("CT室", 16, ["CT检查"]), ("抢救室", 28, ["溶栓"]),
                   ("卒中单元", 12, ["收治住院"])]},
        # 创伤 / 超时
        {"name": "黄德", "seq": 17, "channel": "创伤绿通", "h": 5, "m": 40, "still": True,
         "stops": [("分诊台", 6, ["分诊"]), ("抢救室", 40, ["清创"]), ("DR室", 18, ["拍片"]),
                   ("抢救室", 200, ["观察"])]},
        {"name": "刘洋", "seq": 18, "channel": "创伤绿通", "h": 7, "m": 10, "still": True,
         "stops": [("分诊台", 5, ["分诊"]), ("抢救室", 25, ["止血"]), ("DR室", 12, ["拍片"]),
                   ("抢救室", 160, ["会诊"])]},
        {"name": "任洁", "seq": 19, "channel": "创伤绿通", "h": 8, "m": 30, "still": True,
         "stops": [("分诊台", 4, ["分诊"]), ("抢救室", 20, ["清创"]), ("手术室", 70, ["急诊手术"])]},
        {"name": "姚军", "seq": 20, "channel": "创伤绿通", "h": 9, "m": 50, "still": False,
         "stops": [("分诊台", 5, ["分诊"]), ("抢救室", 22, ["包扎"]), ("DR室", 14, ["拍片"]),
                   ("观察室", 50, ["留观"]), ("收费处", 2, ["离院"])]},
        {"name": "卢倩", "seq": 21, "channel": "创伤绿通", "h": 10, "m": 40, "still": True,
         "stops": [("分诊台", 3, ["分诊"]), ("抢救室", 16, ["评估"]), ("DR室", 10, ["拍片"])]},
        {"name": "钟斌", "seq": 22, "channel": "创伤绿通", "h": 6, "m": 10, "still": True,
         "stops": [("分诊台", 4, ["分诊"]), ("抢救室", 18, ["抗休克"]), ("CT室", 20, ["CT检查"]),
                   ("ICU", 40, ["收治住院"])]},
        # 孕产妇 / 儿科 / 普通急诊
        {"name": "田甜", "seq": 23, "channel": "孕产妇绿通", "h": 7, "m": 50, "still": True,
         "stops": [("分诊台", 3, ["分诊"]), ("抢救室", 10, ["产科会诊"]), ("产科", 40, ["产房准备"])]},
        {"name": "何琳", "seq": 24, "channel": "孕产妇绿通", "h": 9, "m": 5, "still": True,
         "stops": [("分诊台", 4, ["分诊"]), ("产科", 55, ["分娩"]), ("病房", 15, ["收治住院"])]},
        {"name": "苏晴", "seq": 25, "channel": "孕产妇绿通", "h": 11, "m": 20, "still": True,
         "stops": [("分诊台", 5, ["分诊"]), ("抢救室", 8, ["评估"])]},
        {"name": "马超", "seq": 26, "channel": "儿科绿通", "h": 8, "m": 15, "still": True,
         "stops": [("分诊台", 4, ["分诊"]), ("儿科急诊", 35, ["儿科接诊"])]},
        {"name": "许梅", "seq": 27, "channel": "儿科绿通", "h": 9, "m": 35, "still": False,
         "stops": [("分诊台", 3, ["分诊"]), ("儿科急诊", 25, ["雾化"]), ("观察室", 40, ["留观"]),
                   ("收费处", 2, ["离院"])]},
        {"name": "罗浩", "seq": 28, "channel": "儿科绿通", "h": 10, "m": 55, "still": True,
         "stops": [("分诊台", 6, ["分诊"])]},
        {"name": "邓凯", "seq": 29, "channel": "急诊绿通", "h": 6, "m": 30, "still": True,
         "stops": [("分诊台", 5, ["分诊"]), ("抢救室", 28, ["呼吸支持"]), ("CT室", 16, ["CT检查"]),
                   ("ICU", 40, ["收治住院"])]},
        {"name": "贾斌", "seq": 30, "channel": "急诊绿通", "h": 8, "m": 42, "still": False,
         "stops": [("分诊台", 4, ["分诊"]), ("抢救室", 20, ["输液"]), ("观察室", 45, ["留观"]),
                   ("收费处", 2, ["离院"])]},
        {"name": "崔丽", "seq": 31, "channel": "急诊绿通", "h": 9, "m": 28, "still": True,
         "stops": [("分诊台", 5, ["分诊"]), ("检验科", 12, ["抽血"]), ("观察室", 30, ["留观"])]},
        {"name": "彭飞", "seq": 32, "channel": "创伤绿通", "h": 10, "m": 8, "still": True,
         "stops": [("分诊台", 3, ["分诊"]), ("抢救室", 14, ["评估"]), ("手术室", 40, ["急诊手术"])]},
        {"name": "万霞", "seq": 33, "channel": "胸痛绿通", "h": 11, "m": 32, "still": True,
         "stops": [("分诊台", 4, ["分诊"])]},
        {"name": "侯宇", "seq": 34, "channel": "卒中绿通", "h": 11, "m": 40, "still": True,
         "stops": [("分诊台", 3, ["分诊"]), ("抢救室", 7, ["溶栓评估"])]},
        {"name": "龚娜", "seq": 35, "channel": "急诊绿通", "h": 7, "m": 0, "still": False,
         "stops": [("分诊台", 6, ["分诊"]), ("抢救室", 15, ["心电图"]), ("观察室", 80, ["留观"]),
                   ("收费处", 2, ["离院"])]},
        {"name": "严波", "seq": 36, "channel": "胸痛绿通", "h": 5, "m": 55, "still": True,
         "stops": [("分诊台", 4, ["分诊"]), ("抢救室", 14, ["心电图"]), ("CT室", 12, ["CT检查"]),
                   ("介入室", 48, ["介入治疗"]), ("CCU", 30, ["收治住院"])]},
        {"name": "黎娜", "seq": 37, "channel": "卒中绿通", "h": 4, "m": 50, "still": True,
         "stops": [("分诊台", 5, ["分诊"]), ("CT室", 14, ["CT检查"]), ("抢救室", 40, ["溶栓"]),
                   ("卒中单元", 20, ["收治住院"])]},
    ]
    records: list[dict[str, Any]] = []
    patients: dict[str, dict[str, str]] = {}
    for spec in specs:
        no, epc = _ids(spec["seq"])
        t0 = today.replace(hour=spec["h"], minute=spec["m"])
        patients[no] = {"name": spec["name"], "epc": epc, "channel": spec["channel"], "day": "today"}
        records.extend(play_path(t0, spec["name"], no, epc, spec["stops"], still=spec["still"]))
    return records, patients


def _yesterday(today: datetime) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
    """昨天已完成病例，便于按时间范围对比。"""
    day = today - timedelta(days=1)
    specs = [
        {"name": "昨日胸痛-孙琪", "seq": 1, "channel": "胸痛绿通", "h": 8, "m": 10,
         "stops": [("分诊台", 5, ["分诊"]), ("抢救室", 20, ["心电图"]), ("CT室", 12, ["CT检查"]),
                   ("介入室", 50, ["介入治疗"]), ("CCU", 15, ["收治住院"])]},
        {"name": "昨日胸痛-钱坤", "seq": 2, "channel": "胸痛绿通", "h": 10, "m": 40,
         "stops": [("分诊台", 6, ["分诊"]), ("抢救室", 35, ["心电图", "会诊"]), ("观察室", 60, ["留观"]),
                   ("收费处", 2, ["离院"])]},
        {"name": "昨日卒中-冯川", "seq": 3, "channel": "卒中绿通", "h": 7, "m": 15,
         "stops": [("分诊台", 4, ["分诊"]), ("CT室", 15, ["CT检查"]), ("抢救室", 30, ["溶栓"]),
                   ("卒中单元", 12, ["收治住院"])]},
        {"name": "昨日卒中-韩雪", "seq": 4, "channel": "卒中绿通", "h": 13, "m": 5,
         "stops": [("分诊台", 5, ["分诊"]), ("抢救室", 18, ["溶栓评估"]), ("CT室", 20, ["CT检查"]),
                   ("卒中单元", 10, ["收治住院"])]},
        {"name": "昨日创伤-魏峰", "seq": 5, "channel": "创伤绿通", "h": 9, "m": 20,
         "stops": [("分诊台", 4, ["分诊"]), ("抢救室", 22, ["清创"]), ("DR室", 16, ["拍片"]),
                   ("手术室", 80, ["急诊手术"]), ("ICU", 20, ["收治住院"])]},
        {"name": "昨日创伤-吕娟", "seq": 6, "channel": "创伤绿通", "h": 15, "m": 30,
         "stops": [("分诊台", 7, ["分诊"]), ("抢救室", 40, ["观察"]), ("观察室", 55, ["留观"]),
                   ("收费处", 2, ["离院"])]},
        {"name": "昨日儿科-陶陶", "seq": 7, "channel": "儿科绿通", "h": 11, "m": 0,
         "stops": [("分诊台", 4, ["分诊"]), ("儿科急诊", 30, ["儿科接诊"]), ("观察室", 40, ["留观"]),
                   ("收费处", 2, ["离院"])]},
        {"name": "昨日产科-秦悦", "seq": 8, "channel": "孕产妇绿通", "h": 2, "m": 40,
         "stops": [("分诊台", 3, ["分诊"]), ("产科", 70, ["分娩"]), ("病房", 20, ["收治住院"])]},
        {"name": "昨日急诊-卜成", "seq": 9, "channel": "急诊绿通", "h": 18, "m": 10,
         "stops": [("分诊台", 8, ["分诊"]), ("抢救室", 25, ["输液"]), ("观察室", 50, ["留观"]),
                   ("收费处", 2, ["离院"])]},
        {"name": "昨日胸痛-安然", "seq": 10, "channel": "胸痛绿通", "h": 20, "m": 5,
         "stops": [("分诊台", 5, ["分诊"]), ("抢救室", 16, ["心电图"]), ("CT室", 13, ["CT检查"]),
                   ("介入室", 62, ["介入治疗"]), ("CCU", 18, ["收治住院"])]},
    ]
    records: list[dict[str, Any]] = []
    patients: dict[str, dict[str, str]] = {}
    for spec in specs:
        no, epc = _ids(spec["seq"], prefix="MZ20260607", epc_prefix="E20000990000")
        t0 = day.replace(hour=spec["h"], minute=spec["m"])
        patients[no] = {"name": spec["name"], "epc": epc, "channel": spec["channel"], "day": "yesterday"}
        records.extend(play_path(t0, spec["name"], no, epc, spec["stops"], still=False))
    return records, patients


def build_records(now: datetime | None = None) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
    now = now or datetime.now().replace(second=0, microsecond=0)
    today = now.replace(hour=0, minute=0)
    records, patients = _core_patients(now, today)
    extra_r, extra_p = _extra_today(today)
    y_r, y_p = _yesterday(today)
    records.extend(extra_r)
    records.extend(y_r)
    patients.update(extra_p)
    patients.update(y_p)
    records.sort(key=lambda r: r["createTime"])

    by_no: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        by_no[row["hospitalNo"]].append(row)
    for no, meta in patients.items():
        meta["currentLocation"] = infer_current_location(by_no.get(no, []))
    return records, patients


RECORDS, PATIENTS = build_records()


def filter_records(
    hospital_no: str | None = None,
    epc: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    records: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """对应 getInOutMergeList 的业务过滤规则。"""
    rows = records if records is not None else RECORDS
    if not hospital_no and not epc:
        return []

    out = []
    for row in rows:
        if hospital_no and hospital_no not in (row["hospitalNo"], row["patientName"]):
            continue
        if epc and row["wristbandEpc"] != epc:
            continue
        if start_time and end_time:
            if not (start_time <= row["createTime"] <= end_time):
                continue
        out.append(deepcopy(row))
    return out


def find_patient_no(keyword: str) -> str | None:
    keyword = (keyword or "").strip()
    if not keyword:
        return None
    if keyword in PATIENTS:
        return keyword
    for no, meta in PATIENTS.items():
        if keyword in (meta["name"], meta["epc"], no):
            return no
    return None


def patients_in_area(area_name: str) -> list[dict[str, str]]:
    area_name = (area_name or "").strip()
    hits = []
    for no, meta in PATIENTS.items():
        if meta.get("currentLocation") == area_name:
            hits.append({"hospitalNo": no, **meta})
    return hits


def patients_by_channel(channel: str) -> list[dict[str, str]]:
    channel = (channel or "").strip()
    hits = []
    for no, meta in PATIENTS.items():
        if channel and channel not in meta.get("channel", ""):
            continue
        hits.append({"hospitalNo": no, **meta})
    return hits
