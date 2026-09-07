"""工业园区人员安全与作业合规 Skill（本地 mock，可替换真实 API）。"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any

try:
    from langchain_core.tools import tool
except ImportError:
    def tool(fn):
        fn.invoke = lambda args=None, **kwargs: fn(**(args or {}), **kwargs) if isinstance(args, dict) else (fn(args, **kwargs) if args is not None else fn(**kwargs))
        fn.name = fn.__name__
        fn.description = (fn.__doc__ or "").strip()
        return fn


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


NOW = datetime.now().replace(second=0, microsecond=0)
DEPARTMENTS = [
    {"id": "D01", "name": "生产运行部", "parentId": "ROOT"},
    {"id": "D02", "name": "设备维护部", "parentId": "ROOT"},
    {"id": "D03", "name": "安全环保部", "parentId": "ROOT"},
    {"id": "D04", "name": "仓储物流部", "parentId": "ROOT"},
]
EMPLOYEES = [
    {"name": "张伟", "employeeNo": "E1001", "department": "生产运行部", "position": "主操", "cardSn": "CARD-A001", "phone": "138****1001", "status": "在岗"},
    {"name": "李敏", "employeeNo": "E1002", "department": "生产运行部", "position": "巡检员", "cardSn": "CARD-A002", "phone": "138****1002", "status": "在岗"},
    {"name": "王强", "employeeNo": "E2001", "department": "设备维护部", "position": "维修电工", "cardSn": "CARD-B001", "phone": "138****2001", "status": "在岗"},
    {"name": "赵静", "employeeNo": "E3001", "department": "安全环保部", "position": "安全工程师", "cardSn": "CARD-C001", "phone": "138****3001", "status": "在岗"},
    {"name": "陈磊", "employeeNo": "E4001", "department": "仓储物流部", "position": "叉车司机", "cardSn": "CARD-D001", "phone": "138****4001", "status": "休班"},
]
CONTRACTORS = [
    {"contractorId": "C01", "name": "华安检修工程有限公司", "level": "A", "contact": "周经理", "status": "准入有效"},
    {"contractorId": "C02", "name": "恒达防腐保温有限公司", "level": "B", "contact": "刘经理", "status": "准入有效"},
]
CONTRACTOR_STAFF = [
    {"name": "周建国", "staffNo": "C01-018", "contractor": "华安检修工程有限公司", "position": "焊工", "cardSn": "CARD-X018", "certificate": "焊接与热切割", "status": "在场"},
    {"name": "刘海", "staffNo": "C02-006", "contractor": "恒达防腐保温有限公司", "position": "高处作业工", "cardSn": "CARD-X026", "certificate": "高处作业", "status": "在场"},
]
VISITORS = [{"name": "孙悦", "company": "安科技术", "host": "赵静", "purpose": "安全系统调研", "visitTime": NOW.strftime("%Y-%m-%d 09:20"), "status": "已入园"}]
LOCATIONS = [
    {"person": "张伟", "personType": "员工", "department": "生产运行部", "region": "一号装置区", "floor": "1F", "online": True, "lastSeen": NOW.strftime("%Y-%m-%d %H:%M")},
    {"person": "李敏", "personType": "员工", "department": "生产运行部", "region": "罐区", "floor": "1F", "online": True, "lastSeen": NOW.strftime("%Y-%m-%d %H:%M")},
    {"person": "王强", "personType": "员工", "department": "设备维护部", "region": "配电室", "floor": "1F", "online": True, "lastSeen": NOW.strftime("%Y-%m-%d %H:%M")},
    {"person": "赵静", "personType": "员工", "department": "安全环保部", "region": "中控楼", "floor": "2F", "online": True, "lastSeen": NOW.strftime("%Y-%m-%d %H:%M")},
    {"person": "周建国", "personType": "承包商", "department": "华安检修工程有限公司", "region": "受限空间作业区", "floor": "1F", "online": True, "lastSeen": NOW.strftime("%Y-%m-%d %H:%M")},
    {"person": "刘海", "personType": "承包商", "department": "恒达防腐保温有限公司", "region": "二号装置区", "floor": "3F", "online": True, "lastSeen": NOW.strftime("%Y-%m-%d %H:%M")},
]


def _history(person: str) -> list[dict[str, Any]]:
    route = ["厂区东门", "安全教育室", "中控楼", "一号装置区"]
    return [{"person": person, "region": r, "enterTime": (NOW - timedelta(minutes=180-i*42)).strftime("%Y-%m-%d %H:%M"), "stayMinutes": 35 + i*8} for i, r in enumerate(route)]


TICKETS = [
    {"ticketNo": "WT-20260902-001", "type": "动火作业票", "department": "设备维护部", "contractor": "华安检修工程有限公司", "workArea": "一号装置区", "owner": "王强", "status": "作业中", "startTime": NOW.strftime("%Y-%m-%d 08:00"), "compliant": True, "score": 96},
    {"ticketNo": "WT-20260902-002", "type": "受限空间作业票", "department": "生产运行部", "contractor": "华安检修工程有限公司", "workArea": "受限空间作业区", "owner": "张伟", "status": "作业中", "startTime": NOW.strftime("%Y-%m-%d 09:10"), "compliant": False, "score": 72},
    {"ticketNo": "WT-20260902-003", "type": "高处作业票", "department": "设备维护部", "contractor": "恒达防腐保温有限公司", "workArea": "二号装置区", "owner": "王强", "status": "待验收", "startTime": NOW.strftime("%Y-%m-%d 07:30"), "compliant": False, "score": 78},
]
VIOLATIONS = {
    "WT-20260902-002": ["监护人短时离岗", "气体检测复测超时"],
    "WT-20260902-003": ["安全带定位与作业面不一致"],
}
ALARMS = [
    {"alarmId": "A001", "type": "越界报警", "person": "刘海", "region": "二号装置区", "startTime": (NOW-timedelta(minutes=38)).strftime("%Y-%m-%d %H:%M"), "durationMinutes": 12, "handled": True},
    {"alarmId": "A002", "type": "长时间静止", "person": "周建国", "region": "受限空间作业区", "startTime": (NOW-timedelta(minutes=22)).strftime("%Y-%m-%d %H:%M"), "durationMinutes": 22, "handled": False},
    {"alarmId": "A003", "type": "低电量报警", "person": "李敏", "region": "罐区", "startTime": (NOW-timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M"), "durationMinutes": 15, "handled": False},
]
DEVICES = [
    {"deviceNo": "BS-001", "name": "一号装置区基站", "type": "基站", "region": "一号装置区", "online": True, "battery": None},
    {"deviceNo": "CARD-A002", "name": "李敏定位卡", "type": "人员卡", "region": "罐区", "online": True, "battery": 18},
    {"deviceNo": "BEACON-07", "name": "配电室信标", "type": "信标", "region": "配电室", "online": False, "battery": 62},
]


def _match(rows, keyword="", **filters):
    result = []
    for row in rows:
        if keyword and keyword not in " ".join(str(v) for v in row.values()):
            continue
        if any(value and str(value) not in str(row.get(key, "")) for key, value in filters.items()):
            continue
        result.append(row)
    return result


def _result(rows, **extra):
    return _dumps({"count": len(rows), "data": rows, **extra})


def _expand_demo_data():
    """扩展为会议演示规模，同时保持数据确定性。"""
    dept_positions = {
        "生产运行部":["主操","副操","巡检员"], "设备维护部":["维修电工","仪表工","机械检修"],
        "安全环保部":["安全工程师","环保专员"], "仓储物流部":["叉车司机","库管员"],
    }
    surnames = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
    given = ["伟","敏","强","磊","静","超","军","杰","涛","芳","峰","宇","凯","鹏","琳"]
    base = len(EMPLOYEES)
    for i in range(55):
        dept = list(dept_positions)[i % len(dept_positions)]; position = dept_positions[dept][i % len(dept_positions[dept])]
        EMPLOYEES.append({"name":surnames[i%len(surnames)]+given[(i*3)%len(given)], "employeeNo":f"E{base+i+1001:04d}", "department":dept, "position":position, "cardSn":f"CARD-{base+i+101:04d}", "phone":f"139****{3000+i:04d}", "status":"在岗" if i%7 else "休班"})
    companies = ["华安检修工程有限公司","恒达防腐保温有限公司","西域电力建设有限公司","天诚自动化工程有限公司","安泰消防技术有限公司","北方设备安装有限公司"]
    jobs = ["焊工","高处作业工","电工","脚手架工","仪表工","监护人"]
    for i in range(34):
        company=companies[i%len(companies)]
        CONTRACTOR_STAFF.append({"name":surnames[(i+9)%len(surnames)]+given[(i+5)%len(given)],"staffNo":f"C{i%6+1:02d}-{100+i:03d}","contractor":company,"position":jobs[i%len(jobs)],"cardSn":f"CARD-X{100+i:03d}","certificate":jobs[i%len(jobs)],"status":"在场" if i%5 else "离场"})
    for i, company in enumerate(companies[2:], start=3):
        CONTRACTORS.append({"contractorId":f"C{i:02d}","name":company,"level":"A" if i%2 else "B","contact":surnames[i]+"经理","status":"准入有效"})
    regions=["一号装置区","二号装置区","罐区","配电室","中控楼","受限空间作业区","仓储区","热力站"]
    known={x["person"] for x in LOCATIONS}
    people=[(x["name"],"员工",x["department"]) for x in EMPLOYEES if x["status"]=="在岗"]+[(x["name"],"承包商",x["contractor"]) for x in CONTRACTOR_STAFF if x["status"]=="在场"]
    for i,(name,ptype,dept) in enumerate(people):
        if name not in known: LOCATIONS.append({"person":name,"personType":ptype,"department":dept,"region":regions[i%len(regions)],"floor":"1F" if i%4 else "2F","online":i%11!=0,"lastSeen":(NOW-timedelta(minutes=i%9)).strftime("%Y-%m-%d %H:%M")})
    for i in range(20):
        VISITORS.append({"name":surnames[(i+4)%len(surnames)]+given[i%len(given)],"company":f"来访单位{i%6+1}","host":EMPLOYEES[i%len(EMPLOYEES)]["name"],"purpose":["设备交流","安全检查","项目洽谈","技术服务"][i%4],"visitTime":(NOW-timedelta(minutes=i*17)).strftime("%Y-%m-%d %H:%M"),"status":"已入园" if i%3 else "已离园"})
    ticket_types=["动火作业票","受限空间作业票","高处作业票","临时用电作业票","吊装作业票","设备检修票"]
    for i in range(47):
        compliant=i%5 not in {0,1}; no=f"WT-{NOW:%Y%m%d}-{i+10:03d}"
        TICKETS.append({"ticketNo":no,"type":ticket_types[i%len(ticket_types)],"department":list(dept_positions)[i%4],"contractor":companies[i%len(companies)],"workArea":regions[i%len(regions)],"owner":EMPLOYEES[i%len(EMPLOYEES)]["name"],"status":["作业中","待验收","已关闭","待许可"][i%4],"startTime":(NOW-timedelta(minutes=i*23)).strftime("%Y-%m-%d %H:%M"),"compliant":compliant,"score":96-(i%8)*4})
        if not compliant: VIOLATIONS[no]=[["监护人短时离岗","气体检测复测超时","人员定位与作业区域不一致","作业票签字不完整"][i%4]]
    alarm_types=["越界报警","长时间静止","低电量报警","SOS报警","缺员报警","聚集报警","超员报警"]
    for i in range(32):
        p=LOCATIONS[i%len(LOCATIONS)]; ALARMS.append({"alarmId":f"A{i+10:03d}","type":alarm_types[i%7],"person":p["person"],"region":p["region"],"startTime":(NOW-timedelta(minutes=8+i*11)).strftime("%Y-%m-%d %H:%M"),"durationMinutes":5+i%42,"handled":i%4!=0})
    device_types=["基站","人员卡","信标","车载定位终端"]
    for i in range(77): DEVICES.append({"deviceNo":f"DEV-{i+10:03d}","name":f"{regions[i%len(regions)]}{device_types[i%4]}{i+1}","type":device_types[i%4],"region":regions[i%len(regions)],"online":i%13!=0,"battery":None if i%4==0 else 12+(i*7)%88})

_expand_demo_data()


SHIFT_TEMPLATES = {
    "白班": (8, 0, 8.5),
    "中班": (16, 0, 8.5),
    "夜班": (0, 0, 8.5),
}


def _build_attendance_demo_data(days: int = 31):
    """生成可按人、日期检索且能相互校验的排班、考勤和门禁模拟数据。"""
    schedules: list[dict[str, Any]] = []
    attendances: list[dict[str, Any]] = []
    access_records: list[dict[str, Any]] = []
    today_overrides = {
        "E1001": "正常",
        "E1002": "正常",
        "E2001": "迟到",
        "E3001": "早退",
        "E4001": "休班",
    }

    for days_ago in range(days):
        work_date = (NOW - timedelta(days=days_ago)).date()
        date_text = work_date.isoformat()
        for index, employee in enumerate(EMPLOYEES):
            employee_no = employee["employeeNo"]
            rest_day = (work_date.toordinal() + index) % 6 == 0
            if employee["department"] == "生产运行部":
                shift = ("白班", "中班", "夜班")[(work_date.toordinal() + index) % 3]
            else:
                shift = "白班"

            status = "休班" if rest_day else "正常"
            anomaly = (index * 7 + days_ago * 3) % 29
            if not rest_day:
                if anomaly == 0:
                    status = "迟到"
                elif anomaly == 1:
                    status = "早退"
                elif anomaly == 2:
                    status = "缺卡"
                elif anomaly == 3:
                    status = "缺勤"
            if days_ago == 0 and employee_no in today_overrides:
                status = today_overrides[employee_no]

            schedule_id = f"SCH-{date_text.replace('-', '')}-{employee_no}"
            if status == "休班":
                scheduled_start = scheduled_end = None
                schedule_shift = "休班"
            else:
                hour, minute, duration_hours = SHIFT_TEMPLATES[shift]
                scheduled_start_dt = datetime.combine(work_date, datetime.min.time()).replace(hour=hour, minute=minute)
                scheduled_end_dt = scheduled_start_dt + timedelta(hours=duration_hours)
                scheduled_start = scheduled_start_dt.strftime("%Y-%m-%d %H:%M")
                scheduled_end = scheduled_end_dt.strftime("%Y-%m-%d %H:%M")
                schedule_shift = shift

            schedules.append({
                "scheduleId": schedule_id,
                "person": employee["name"],
                "employeeNo": employee_no,
                "department": employee["department"],
                "date": date_text,
                "shift": schedule_shift,
                "start": scheduled_start,
                "end": scheduled_end,
            })

            clock_in_dt = clock_out_dt = None
            late_minutes = early_leave_minutes = 0
            work_hours = overtime_hours = 0.0
            if scheduled_start and scheduled_end:
                start_dt = datetime.strptime(scheduled_start, "%Y-%m-%d %H:%M")
                end_dt = datetime.strptime(scheduled_end, "%Y-%m-%d %H:%M")
                if status == "正常":
                    clock_in_dt = start_dt - timedelta(minutes=5 + index % 8)
                    clock_out_dt = end_dt + timedelta(minutes=6 + index % 15)
                elif status == "迟到":
                    late_minutes = 11 + index % 13
                    clock_in_dt = start_dt + timedelta(minutes=late_minutes)
                    clock_out_dt = end_dt + timedelta(minutes=5)
                elif status == "早退":
                    early_leave_minutes = 18 + index % 17
                    clock_in_dt = start_dt - timedelta(minutes=6)
                    clock_out_dt = end_dt - timedelta(minutes=early_leave_minutes)
                elif status == "缺卡":
                    clock_in_dt = start_dt - timedelta(minutes=4)

                if clock_in_dt and clock_out_dt:
                    work_hours = round((clock_out_dt - clock_in_dt).total_seconds() / 3600, 2)
                    overtime_hours = round(max(0, (clock_out_dt - end_dt).total_seconds() / 3600), 2)

            attendance = {
                "attendanceId": f"ATT-{date_text.replace('-', '')}-{employee_no}",
                "person": employee["name"],
                "employeeNo": employee_no,
                "department": employee["department"],
                "date": date_text,
                "shift": schedule_shift,
                "scheduledStart": scheduled_start,
                "scheduledEnd": scheduled_end,
                "clockIn": clock_in_dt.strftime("%Y-%m-%d %H:%M") if clock_in_dt else None,
                "clockOut": clock_out_dt.strftime("%Y-%m-%d %H:%M") if clock_out_dt else None,
                "lateMinutes": late_minutes,
                "earlyLeaveMinutes": early_leave_minutes,
                "workHours": work_hours,
                "overtimeHours": overtime_hours,
                "status": status,
                "source": "模拟考勤机",
            }
            attendances.append(attendance)

            if clock_in_dt:
                access_records.append({
                    "recordId": f"ACS-IN-{date_text.replace('-', '')}-{employee_no}",
                    "person": employee["name"], "employeeNo": employee_no,
                    "department": employee["department"], "date": date_text,
                    "gate": "厂区东门", "direction": "进入",
                    "time": (clock_in_dt - timedelta(minutes=3)).strftime("%Y-%m-%d %H:%M"),
                    "result": "通过",
                })
            if clock_out_dt:
                access_records.append({
                    "recordId": f"ACS-OUT-{date_text.replace('-', '')}-{employee_no}",
                    "person": employee["name"], "employeeNo": employee_no,
                    "department": employee["department"], "date": date_text,
                    "gate": "厂区东门", "direction": "离开",
                    "time": (clock_out_dt + timedelta(minutes=3)).strftime("%Y-%m-%d %H:%M"),
                    "result": "通过",
                })
    return schedules, attendances, access_records


SCHEDULES, ATTENDANCES, ACCESS_RECORDS = _build_attendance_demo_data()


def _attendance_dates(value: str) -> set[str] | None:
    """把常见自然日期条件转换成演示数据中的日期集合；None 表示不过滤。"""
    text = (value or "今天").strip()
    today = NOW.date()
    if text in {"全部", "all", "ALL"}:
        return None
    if text in {"今天", "今日"}:
        return {today.isoformat()}
    if text in {"昨天", "昨日"}:
        return {(today - timedelta(days=1)).isoformat()}
    if text in {"近7天", "最近7天", "过去7天"}:
        return {(today - timedelta(days=i)).isoformat() for i in range(7)}
    if text in {"近30天", "最近30天", "过去30天"}:
        return {(today - timedelta(days=i)).isoformat() for i in range(30)}
    if text in {"本月", "这个月"}:
        return {
            (today - timedelta(days=i)).isoformat()
            for i in range(31)
            if (today - timedelta(days=i)).month == today.month
        }
    return {text}


def _filter_attendance_rows(rows, person: str = "", date: str = "", **filters):
    dates = _attendance_dates(date)
    selected = [row for row in rows if dates is None or row.get("date") in dates]
    return _match(selected, person, **filters)


ASSET_LOCATIONS = [
    {"asset": name, "assetNo": f"AST-{i:03d}", "assetType": asset_type, "department": department,
     "region": region, "floor": "1F" if i % 5 else "2F", "online": i % 11 != 0,
     "status": "越界" if i == 7 else "离线" if i % 11 == 0 else "正常",
     "lastSeen": (NOW - timedelta(minutes=i % 9)).strftime("%Y-%m-%d %H:%M")}
    for i, (name, asset_type, department, region) in enumerate([
        ("便携式气体检测仪01", "安全仪器", "安全环保部", "受限空间作业区"),
        ("红外测温仪02", "巡检仪器", "设备维护部", "配电室"),
        ("移动检修电源03", "检修设备", "设备维护部", "一号装置区"),
        ("防爆对讲机04", "通信设备", "生产运行部", "罐区"),
        ("空气呼吸器05", "应急装备", "安全环保部", "安全教育室"),
        ("高压清洗机06", "检修设备", "设备维护部", "二号装置区"),
        ("移动脚手架07", "作业装备", "设备维护部", "仓储区"),
        ("便携照明灯08", "应急装备", "生产运行部", "罐区北侧"),
        ("阀门诊断仪09", "巡检仪器", "设备维护部", "热力站"),
        ("叉车10号", "车辆", "仓储物流部", "仓储区"),
        ("移动排水泵11", "应急装备", "安全环保部", "二号装置区"),
        ("扭矩扳手12", "检修工具", "设备维护部", "一号装置区"),
    ], 1)
]


def _asset_history(asset: str):
    found = next((row for row in ASSET_LOCATIONS if asset in {row["asset"], row["assetNo"]}), None)
    if not found:
        return []
    regions = ["仓储区", "安全教育室", found["department"], found["region"]]
    return [
        {"asset": found["asset"], "assetNo": found["assetNo"], "region": region,
         "enterTime": (NOW - timedelta(minutes=210 - i * 56)).strftime("%Y-%m-%d %H:%M"),
         "stayMinutes": 28 + i * 11}
        for i, region in enumerate(regions)
    ]


@tool
def query_employees(keyword: str = "", department: str = "", position: str = "") -> str:
    """查询内部员工档案：姓名、工号、部门、岗位、定位卡 SN。"""
    return _result(_match(EMPLOYEES, keyword, department=department, position=position))

@tool
def query_contractor_staff(keyword: str = "", contractor: str = "") -> str:
    """查询承包商人员档案、证书和在场状态。"""
    return _result(_match(CONTRACTOR_STAFF, keyword, contractor=contractor))

@tool
def query_contractors(keyword: str = "") -> str:
    """查询承包商单位信息和准入状态。"""
    return _result(_match(CONTRACTORS, keyword))

@tool
def query_departments(keyword: str = "") -> str:
    """查询部门组织架构。"""
    return _result(_match(DEPARTMENTS, keyword))

@tool
def query_visitors(keyword: str = "", status: str = "") -> str:
    """查询访客入园记录。"""
    return _result(_match(VISITORS, keyword, status=status))

@tool
def summarize_employees(group_by: str = "department") -> str:
    """按 department 或 position 统计内部员工在册人数。"""
    key = "position" if group_by == "position" else "department"
    return _result([{"name": k, "count": v} for k, v in Counter(x[key] for x in EMPLOYEES).items()], groupBy=key)

@tool
def query_locations_realtime(keyword: str = "", region: str = "", person_type: str = "") -> str:
    """查询人员实时位置，可按姓名、区域、人员类型筛选。"""
    return _result(_match(LOCATIONS, keyword, region=region, personType=person_type), asOf=NOW.strftime("%Y-%m-%d %H:%M"), dataSource="园区人员定位模拟接口")

@tool
def query_locations_history(person: str, start_time: str = "", end_time: str = "") -> str:
    """查询单人历史轨迹和区域停留。"""
    return _result(_history(person), person=person, dataSource="园区人员定位模拟接口")

@tool
def query_region_enter_leave(person: str, region: str = "") -> str:
    """查询单人区域进出明细。"""
    rows = _history(person)
    if region: rows = [x for x in rows if region in x["region"]]
    return _result(rows, person=person)

@tool
def query_region_enter_leave_summary(region: str = "", group_by: str = "region") -> str:
    """汇总区域人员进出次数。"""
    counts = Counter(x["region"] for p in LOCATIONS for x in _history(p["person"]))
    rows = [{"region": k, "enterCount": v, "leaveCount": max(0, v-1)} for k, v in counts.items() if not region or region in k]
    return _result(rows)

@tool
def query_asset_locations_realtime(keyword: str = "", region: str = "", asset_type: str = "") -> str:
    """查询人员安全场景资产实时位置，可按名称/编号、区域和资产类型筛选。"""
    rows = _match(ASSET_LOCATIONS, keyword, region=region, assetType=asset_type)
    return _result(rows, asOf=NOW.strftime("%Y-%m-%d %H:%M"), dataSource="园区资产定位模拟接口")

@tool
def query_asset_locations_history(asset: str, start_time: str = "", end_time: str = "") -> str:
    """查询人员安全场景资产历史位置与区域停留。"""
    return _result(_asset_history(asset), asset=asset, dataSource="园区资产定位模拟接口")

@tool
def query_asset_region_enter_leave(asset: str, region: str = "") -> str:
    """查询人员安全场景资产区域进出明细。"""
    rows = [row for row in _asset_history(asset) if not region or region in row["region"]]
    return _result(rows, asset=asset)

@tool
def query_online_persons(region: str = "", person_type: str = "") -> str:
    """统计当前在线人员。"""
    rows = _match([x for x in LOCATIONS if x["online"]], "", region=region, personType=person_type)
    return _result(rows, onlineCount=len(rows))

@tool
def list_work_tickets(keyword: str = "", ticket_no: str = "", status: str = "", ticket_type: str = "") -> str:
    """查询原始作业票清单或单票详情。"""
    return _result(_match(TICKETS, keyword, ticketNo=ticket_no, status=status, type=ticket_type))

@tool
def summarize_work_tickets(group_by: str = "type") -> str:
    """按票种、部门、承包商或状态聚合作业票。"""
    key = group_by if group_by in {"type", "department", "contractor", "status"} else "type"
    return _result([{"name": k, "count": v} for k, v in Counter(x[key] for x in TICKETS).items()], groupBy=key)

@tool
def list_work_ticket_compliance(compliant: str = "", ticket_type: str = "") -> str:
    """查询作业票合规结果清单。"""
    rows = [dict(x, violations=VIOLATIONS.get(x["ticketNo"], [])) for x in TICKETS]
    if compliant: rows = [x for x in rows if x["compliant"] == (compliant.lower() in {"true", "1", "yes", "合规"})]
    return _result(_match(rows, "", type=ticket_type))

@tool
def summarize_work_ticket_compliance() -> str:
    """汇总作业票合规率。"""
    ok = sum(x["compliant"] for x in TICKETS)
    return _dumps({"total": len(TICKETS), "compliant": ok, "nonCompliant": len(TICKETS)-ok, "complianceRate": round(ok/len(TICKETS)*100, 1)})

@tool
def trend_work_ticket_compliance(period: str = "day", days: int = 7) -> str:
    """生成作业票合规率日/月趋势。"""
    rows = [{"date": (NOW-timedelta(days=i)).strftime("%Y-%m-%d"), "complianceRate": 88 + (i*3)%11} for i in range(min(days, 31)-1, -1, -1)]
    return _result(rows, period=period)

@tool
def group_work_ticket_compliance(group_by: str = "type") -> str:
    """按票种、部门或承包商分组合规统计。"""
    key = group_by if group_by in {"type", "department", "contractor"} else "type"; groups = defaultdict(list)
    for x in TICKETS: groups[x[key]].append(x)
    return _result([{"name": k, "total": len(v), "compliant": sum(x["compliant"] for x in v), "rate": round(sum(x["compliant"] for x in v)/len(v)*100, 1)} for k,v in groups.items()])

@tool
def rank_work_ticket_compliance_rules(limit: int = 10) -> str:
    """排行高频违规规则。"""
    counts = Counter(v for values in VIOLATIONS.values() for v in values)
    return _result([{"rule": k, "count": v} for k,v in counts.most_common(limit)])

@tool
def get_work_ticket_compliance_detail(ticket_no: str) -> str:
    """获取单票合规报告。"""
    rows = _match(TICKETS, "", ticketNo=ticket_no)
    return _dumps({"ok": bool(rows), "ticket": rows[0] if rows else None, "violations": VIOLATIONS.get(ticket_no, []), "suggestion": "补齐监护与检测记录后复核" if VIOLATIONS.get(ticket_no) else "持续保持"})

@tool
def get_work_ticket_process_analysis(ticket_no: str) -> str:
    """分析单票审批、许可、作业和验收环节时长。"""
    return _result([{"stage": "申请审批", "minutes": 28}, {"stage": "安全交底", "minutes": 16}, {"stage": "许可确认", "minutes": 12}, {"stage": "现场作业", "minutes": 145}], ticketNo=ticket_no)

@tool
def summarize_alarms() -> str:
    """汇总七类人员安全报警。"""
    base = {k: 0 for k in ["越界报警","长时间静止","低电量报警","SOS报警","缺员报警","聚集报警","超员报警"]}
    base.update(Counter(x["type"] for x in ALARMS))
    return _result([{"type": k, "count": v} for k,v in base.items()], unhandled=sum(not x["handled"] for x in ALARMS))

@tool
def analyze_alarms(alarm_type: str = "", handled: str = "") -> str:
    """分析报警明细、连续报警与处理时长。"""
    rows = _match(ALARMS, "", type=alarm_type)
    if handled: rows = [x for x in rows if x["handled"] == (handled.lower() in {"true","1","yes","已处理"})]
    return _result(rows)

@tool
def query_devices(keyword: str = "", device_type: str = "", online: str = "") -> str:
    """查询定位基站、人员卡和信标等硬件。"""
    rows = _match(DEVICES, keyword, type=device_type)
    if online: rows = [x for x in rows if x["online"] == (online.lower() in {"true","1","yes","在线"})]
    return _result(rows)

@tool
def summarize_devices() -> str:
    """统计定位设备在线率和低电量数量。"""
    online = sum(x["online"] for x in DEVICES); low = sum(x["battery"] is not None and x["battery"] < 20 for x in DEVICES)
    return _dumps({"total": len(DEVICES), "online": online, "offline": len(DEVICES)-online, "onlineRate": round(online/len(DEVICES)*100,1), "lowBattery": low})

@tool
def query_card_bind_records(person: str = "", card_sn: str = "") -> str:
    """查询人员与定位卡绑定记录。"""
    rows = [{"person": x["name"], "personNo": x.get("employeeNo", x.get("staffNo")), "cardSn": x["cardSn"], "bindTime": "2026-08-01 08:00", "status": "有效"} for x in EMPLOYEES+CONTRACTOR_STAFF]
    return _result(_match(rows, person or card_sn))

@tool
def query_attendances(person: str = "", date: str = "", status: str = "", department: str = "") -> str:
    """查询内部员工模拟考勤明细，可按人员、日期、状态和部门筛选；日期支持今天、昨日、近7天、近30天、本月或 YYYY-MM-DD。"""
    rows = _filter_attendance_rows(ATTENDANCES, person, date, status=status, department=department)
    return _result(rows, abnormalCount=sum(x["status"] not in {"正常", "休班"} for x in rows))

@tool
def query_schedules(person: str = "", date: str = "", department: str = "") -> str:
    """查询人员模拟排班，可按人员、日期和部门筛选。"""
    return _result(_filter_attendance_rows(SCHEDULES, person, date, department=department))

@tool
def query_access_records(person: str = "", gate: str = "", date: str = "", direction: str = "") -> str:
    """查询与模拟考勤对应的门禁进出记录，可按人员、日期、门岗和方向筛选。"""
    rows = _filter_attendance_rows(ACCESS_RECORDS, person, date, gate=gate, direction=direction)
    return _result(rows)

@tool
def query_work_ticket_workhour_person(person: str = "", date: str = "") -> str:
    """按人员查询作业票有效工时。"""
    rows = [{"person": "周建国", "ticketNo": "WT-20260902-001", "validHours": 4.2}, {"person": "刘海", "ticketNo": "WT-20260902-003", "validHours": 5.1}]
    return _result(_match(rows, person), totalHours=round(sum(x["validHours"] for x in _match(rows, person)),1))

@tool
def query_work_ticket_workhour_contractor(contractor: str = "", date: str = "") -> str:
    """按承包商单位汇总作业票有效工时。"""
    rows = [{"contractor": "华安检修工程有限公司", "persons": 8, "validHours": 31.6}, {"contractor": "恒达防腐保温有限公司", "persons": 5, "validHours": 22.4}]
    return _result(_match(rows, contractor))

@tool
def query_loitering_sessions(person: str = "", region: str = "") -> str:
    """查询徘徊会话明细。"""
    rows = [{"person": "李敏", "region": "罐区北侧", "startTime": (NOW-timedelta(minutes=70)).strftime("%Y-%m-%d %H:%M"), "durationMinutes": 34, "visits": 6}]
    return _result(_match(rows, person, region=region))

@tool
def query_abnormal_dwell_summary(region: str = "") -> str:
    """一站式汇总异常驻留、徘徊和长时间静止。"""
    return _result([{"region": "罐区北侧", "loitering": 1, "longDwell": 2, "static": 0}, {"region": "受限空间作业区", "loitering": 0, "longDwell": 1, "static": 1}])

@tool
def query_trajectory_distance(person: str, date: str = "") -> str:
    """查询人员轨迹行走距离和时长。"""
    return _dumps({"person": person, "date": date or NOW.strftime("%Y-%m-%d"), "distanceKm": 8.6, "movingMinutes": 214, "regions": 7})

@tool
def query_work_intensity_summary(department: str = "") -> str:
    """汇总部门人员工作强度。"""
    return _result([{"department": "生产运行部", "persons": 18, "avgDistanceKm": 7.8, "highIntensity": 3}, {"department": "设备维护部", "persons": 12, "avgDistanceKm": 9.4, "highIntensity": 4}])

@tool
def query_workload_analysis(person: str = "", department: str = "") -> str:
    """分析劳动强度和疲劳风险。"""
    rows = [{"person": "李敏", "department": "生产运行部", "continuousHours": 3.8, "distanceKm": 10.2, "risk": "中"}, {"person": "王强", "department": "设备维护部", "continuousHours": 5.2, "distanceKm": 12.1, "risk": "高"}]
    return _result(_match(rows, person, department=department))

@tool
def query_inspection_list(keyword: str = "", result: str = "") -> str:
    """查询现场质检和安全检查记录。"""
    rows = [{"inspectionNo": "QC-0902-01", "area": "一号装置区", "item": "动火隔离措施", "inspector": "赵静", "result": "合格", "time": NOW.strftime("%Y-%m-%d 09:30")}, {"inspectionNo": "QC-0902-02", "area": "受限空间作业区", "item": "气体检测复测", "inspector": "赵静", "result": "待整改", "time": NOW.strftime("%Y-%m-%d 10:20")}]
    return _result(_match(rows, keyword, result=result))

@tool
def render_personnel_tree(department: str = "") -> str:
    """生成部门→岗位→人员目录树。"""
    tree = defaultdict(lambda: defaultdict(list))
    for x in EMPLOYEES:
        if not department or department in x["department"]: tree[x["department"]][x["position"]].append(x["name"])
    return _dumps({"tree": [{"department": d, "positions": [{"position": p, "persons": names} for p,names in ps.items()]} for d,ps in tree.items()]})

@tool
def render_personnel_timeline(person: str, date: str = "") -> str:
    """生成人员定位、门禁、作业和报警综合时间线。"""
    rows = [{"time": x["enterTime"], "type": "定位", "event": f"进入{x['region']}"} for x in _history(person)]
    rows.append({"time": NOW.strftime("%Y-%m-%d %H:%M"), "type": "状态", "event": "当前在线"})
    return _result(sorted(rows, key=lambda x: x["time"]), person=person)

@tool
def show_factory_3d_map(keyword: str = "所有", region: str = "") -> str:
    """在一厂区 3D 数字孪生地图显示单人、区域或全部人员实时高精度米级位置。"""
    areas = [
        # 主干生产与装置区（包含精确米级尺寸与建筑高度）
        {"name":"一号装置区","floor":"一厂区","x":215,"y":20,"w":170,"h":120,"heightM":18,"dim":"170m×120m (高18m)","type":"process","tag":"主装置"},
        {"name":"二号装置区","floor":"一厂区","x":410,"y":20,"w":170,"h":120,"heightM":22,"dim":"170m×120m (高22m)","type":"process","tag":"主装置"},
        {"name":"裂解与聚合车间","floor":"一厂区","x":605,"y":20,"w":110,"h":120,"heightM":26,"dim":"110m×120m (高26m)","type":"process","tag":"高温高压"},
        # 储运与危险化学品罐区
        {"name":"罐区","floor":"一厂区","x":215,"y":165,"w":170,"h":130,"heightM":14,"dim":"170m×130m (容积5万m³)","type":"tank","tag":"重大危险源"},
        {"name":"装卸车栈桥","floor":"一厂区","x":410,"y":165,"w":170,"h":60,"heightM":8,"dim":"170m×60m (8车位)","type":"logistics","tag":"防静电区"},
        {"name":"危废暂存间","floor":"一厂区","x":410,"y":235,"w":170,"h":60,"heightM":7,"dim":"170m×60m (防渗隔离)","type":"danger","tag":"防渗隔离"},
        # 动力与受限空间作业区
        {"name":"配电室","floor":"一厂区","x":605,"y":165,"w":110,"h":60,"heightM":6,"dim":"110m×60m (110kV)","type":"power","tag":"高压危险"},
        {"name":"动力泵房","floor":"一厂区","x":605,"y":235,"w":110,"h":60,"heightM":9,"dim":"110m×60m (主辅泵组)","type":"power","tag":"24h运行"},
        {"name":"受限空间作业区","floor":"一厂区","x":110,"y":165,"w":85,"h":130,"heightM":12,"dim":"85m×130m (密闭反应器)","type":"confined","tag":"严格审批"},
        # 综合办公与门禁管理
        {"name":"中控楼","floor":"一厂区","x":110,"y":20,"w":85,"h":120,"heightM":15,"dim":"85m×120m (4层防爆)","type":"control","tag":"防爆控制室"},
        {"name":"安全教育室","floor":"一厂区","x":10,"y":165,"w":80,"h":130,"heightM":6,"dim":"80m×130m (培训中心)","type":"office","tag":"培训准入"},
        {"name":"厂区东门","floor":"一厂区","x":10,"y":20,"w":80,"h":120,"heightM":5,"dim":"80m×120m (人行车行闸)","type":"gate","tag":"人脸道闸"},
    ]
    # 模拟精确米级坐标 (米为单位: x, y)
    PERSON_METRIC_COORDS = {
        "张伟": {"region": "一号装置区", "mx": 275, "my": 75, "mz": "2F"},
        "李敏": {"region": "罐区", "mx": 285, "my": 220, "mz": "1F"},
        "王强": {"region": "配电室", "mx": 650, "my": 195, "mz": "1F"},
        "赵静": {"region": "中控楼", "mx": 145, "my": 65, "mz": "3F"},
        "周建国": {"region": "受限空间作业区", "mx": 150, "my": 230, "mz": "1F"},
        "刘海": {"region": "二号装置区", "mx": 485, "my": 80, "mz": "3F"},
    }
    generic = keyword in {"", "所有", "全部", "所有人员", "人员分布"}
    rows = [x for x in LOCATIONS if (generic or keyword in x["person"]) and (not region or region in x["region"])]
    markers = []
    for x in rows:
        pname = x["person"]
        mcoord = PERSON_METRIC_COORDS.get(pname, {"mx": 300, "my": 80, "mz": x.get("floor", "1F")})
        markers.append({
            "name": pname,
            "identifier": x["department"],
            "position": x["region"],
            "floor": "一厂区",
            "subjectType": x["personType"],
            "status": "在线" if x["online"] else "离线",
            "metricCoord": f"X:{mcoord['mx']}m, Y:{mcoord['my']}m ({mcoord['mz']})",
            "mx": mcoord["mx"],
            "my": mcoord["my"],
            "mz": mcoord["mz"],
        })
    if not markers: return "无法生成地图：未找到匹配人员或区域。"
    return "__MAP__" + _dumps({"mode":"factory-3d", "title":"一厂区 3D 数字孪生真实时空地图", "floor":"一厂区", "subject":keyword or "所有人员", "subjectType":"人员", "position":region or "全厂区", "status":"实时在线", "areas":areas, "markers":markers})


INDUSTRIAL_TOOLS = [value for value in list(globals().values()) if hasattr(value, "name") and value.name in {
    "query_employees","query_contractor_staff","query_contractors","query_departments","query_visitors","summarize_employees",
    "query_locations_realtime","query_locations_history","query_region_enter_leave","query_region_enter_leave_summary","query_online_persons",
    "query_asset_locations_realtime","query_asset_locations_history","query_asset_region_enter_leave",
    "list_work_tickets","summarize_work_tickets","list_work_ticket_compliance","summarize_work_ticket_compliance","trend_work_ticket_compliance",
    "group_work_ticket_compliance","rank_work_ticket_compliance_rules","get_work_ticket_compliance_detail","get_work_ticket_process_analysis",
    "summarize_alarms","analyze_alarms","query_devices","summarize_devices","query_card_bind_records","query_attendances","query_schedules",
    "query_access_records","query_work_ticket_workhour_person","query_work_ticket_workhour_contractor","query_loitering_sessions",
    "query_abnormal_dwell_summary","query_trajectory_distance","query_work_intensity_summary","query_workload_analysis","query_inspection_list",
    "render_personnel_tree","render_personnel_timeline"
    ,"show_factory_3d_map"
}]
