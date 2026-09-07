"""能源企业交流演示数据：电、热、气、调度和安全生产。"""
from __future__ import annotations
import json
from datetime import datetime, timedelta
try:
    from langchain_core.tools import tool
except ImportError:
    def tool(fn):
        fn.invoke = lambda args=None, **kwargs: fn(**(args or {}), **kwargs) if isinstance(args, dict) else (fn(args, **kwargs) if args is not None else fn(**kwargs))
        fn.name = fn.__name__
        fn.description = (fn.__doc__ or "").strip()
        return fn

NOW = datetime.now().replace(second=0, microsecond=0)
def _d(v: Any) -> str: return json.dumps(v, ensure_ascii=False, separators=(",", ":"))
def _rows(rows, **extra): return _d({"count": len(rows), "data": rows, "asOf": NOW.strftime("%Y-%m-%d %H:%M"), **extra})

UNITS = [
    {"plant":"北区热电厂","unit":"1号机组","type":"热电联产","capacityMW":135,"outputMW":112.6,"heatLoadMW":86.4,"status":"运行","coalConsumptionGPerKWh":298.4,"availability":98.7},
    {"plant":"北区热电厂","unit":"2号机组","type":"热电联产","capacityMW":135,"outputMW":126.8,"heatLoadMW":91.2,"status":"运行","coalConsumptionGPerKWh":295.1,"availability":99.1},
    {"plant":"南区电厂","unit":"3号机组","type":"火电","capacityMW":330,"outputMW":286.5,"heatLoadMW":0,"status":"运行","coalConsumptionGPerKWh":289.7,"availability":97.9},
    {"plant":"光伏示范站","unit":"光伏方阵A","type":"光伏","capacityMW":60,"outputMW":41.3,"heatLoadMW":0,"status":"运行","coalConsumptionGPerKWh":0,"availability":99.4},
]
SUBSTATIONS = [
    {"station":"开发区220kV变电站","voltageKv":220,"mainTransformer":"1号主变","loadMW":168.2,"loadRate":76.5,"status":"正常","unhandledAlarm":0},
    {"station":"北工业园110kV变电站","voltageKv":110,"mainTransformer":"2号主变","loadMW":72.8,"loadRate":88.6,"status":"重载关注","unhandledAlarm":1},
    {"station":"南区110kV变电站","voltageKv":110,"mainTransformer":"1号主变","loadMW":54.1,"loadRate":62.3,"status":"正常","unhandledAlarm":0},
]
LINES = [
    {"line":"富北一线","voltageKv":110,"currentA":426,"loadRate":71.2,"temperatureC":43.8,"status":"正常","inspection":"已巡检"},
    {"line":"富工二线","voltageKv":110,"currentA":518,"loadRate":86.4,"temperatureC":58.6,"status":"温升关注","inspection":"待复核"},
    {"line":"园区配一线","voltageKv":10,"currentA":312,"loadRate":64.8,"temperatureC":39.2,"status":"正常","inspection":"已巡检"},
]
OUTAGES = [
    {"eventNo":"OS-0902-01","area":"北工业园三号馈线","type":"计划停电","startTime":(NOW+timedelta(days=1,hours=2)).strftime("%Y-%m-%d %H:%M"),"expectedMinutes":120,"affectedUsers":18,"status":"已通知"},
    {"eventNo":"OS-0901-03","area":"城东配网","type":"故障停电","startTime":(NOW-timedelta(days=1,hours=3)).strftime("%Y-%m-%d %H:%M"),"durationMinutes":36,"affectedUsers":247,"status":"已恢复"},
]
HEAT = [
    {"area":"北区","heatSource":"北区热电厂","supplyTempC":92.4,"returnTempC":51.8,"pressureMpa":0.82,"flowTph":1260,"loadMW":177.6,"status":"稳定"},
    {"area":"开发区","heatSource":"北区热电厂","supplyTempC":89.1,"returnTempC":49.7,"pressureMpa":0.76,"flowTph":860,"loadMW":118.2,"status":"稳定"},
    {"area":"南区","heatSource":"南区调峰锅炉房","supplyTempC":86.7,"returnTempC":47.2,"pressureMpa":0.71,"flowTph":540,"loadMW":72.5,"status":"流量关注"},
]
HEAT_ALARMS = [{"alarmNo":"HA-031","area":"南区二级网","type":"流量偏低","value":72.1,"threshold":80,"startTime":(NOW-timedelta(minutes=34)).strftime("%Y-%m-%d %H:%M"),"handled":False}]
GAS = [
    {"station":"开发区门站","dailySupply10kM3":38.6,"instantFlowM3h":18640,"inletPressureMpa":1.62,"outletPressureMpa":0.38,"odorizerStatus":"正常","status":"运行"},
    {"station":"北区调压站","dailySupply10kM3":21.4,"instantFlowM3h":10280,"inletPressureMpa":0.39,"outletPressureMpa":0.21,"odorizerStatus":"正常","status":"运行"},
]
DISPATCH = [
    {"commandNo":"DC-0902-06","type":"电力调度","target":"南区电厂3号机组","content":"负荷提升20MW","issuedAt":(NOW-timedelta(minutes=42)).strftime("%Y-%m-%d %H:%M"),"deadline":(NOW-timedelta(minutes=12)).strftime("%Y-%m-%d %H:%M"),"status":"已执行"},
    {"commandNo":"DC-0902-07","type":"供热调度","target":"南区调峰锅炉房","content":"二级网流量提升8%","issuedAt":(NOW-timedelta(minutes=18)).strftime("%Y-%m-%d %H:%M"),"deadline":(NOW+timedelta(minutes=12)).strftime("%Y-%m-%d %H:%M"),"status":"执行中"},
]
RISKS = [
    {"riskNo":"R-2026-118","site":"北工业园110kV变电站","category":"设备重载","level":"较大","owner":"输变电运维班","measure":"调整运行方式并开展红外测温","status":"管控中"},
    {"riskNo":"R-2026-119","site":"南区二级热网","category":"流量异常","level":"一般","owner":"热网运行班","measure":"排查阀门与换热站参数","status":"整改中"},
    {"riskNo":"R-2026-120","site":"富工二线","category":"导线温升","level":"一般","owner":"线路运检班","measure":"缩短测温周期并控制负荷","status":"管控中"},
]

def _expand_energy_demo():
    plants=["北区热电厂","南区电厂","东区热电厂","光伏示范站","风电示范场"]
    for i in range(9):
        kind="热电联产" if i%3==0 else ("火电" if i%3==1 else "新能源")
        cap=[135,330,60][i%3]
        UNITS.append({"plant":plants[i%len(plants)],"unit":f"{i+4}号机组","type":kind,"capacityMW":cap,"outputMW":round(cap*(.62+(i%4)*.08),1),"heatLoadMW":round(42+i*5.6,1) if kind=="热电联产" else 0,"status":"检修" if i==7 else "运行","coalConsumptionGPerKWh":0 if kind=="新能源" else round(286+i*1.7,1),"availability":round(96.8+(i%5)*.55,1)})
    for i in range(17):
        voltage=[220,110,35][i%3]; load=round(34+i*7.3,1); rate=round(48+(i*5.7)%48,1)
        SUBSTATIONS.append({"station":f"{['工业园','开发区','城东','城西','北区'][i%5]}{voltage}kV变电站{i+1}","voltageKv":voltage,"mainTransformer":f"{i%3+1}号主变","loadMW":load,"loadRate":rate,"status":"重载关注" if rate>=85 else "正常","unhandledAlarm":1 if i%7==0 else 0})
    for i in range(37):
        rate=round(42+(i*6.1)%53,1)
        LINES.append({"line":f"富能{chr(65+i%12)}线-{i+1}","voltageKv":[110,35,10][i%3],"currentA":210+i*13,"loadRate":rate,"temperatureC":round(31+rate*.31,1),"status":"温升关注" if rate>86 else "正常","inspection":"待复核" if i%9==0 else "已巡检"})
    for i in range(28):
        planned=i%3!=0
        OUTAGES.append({"eventNo":f"OS-{NOW:%m%d}-{i+10:02d}","area":f"{['北工业园','开发区','城东','城西'][i%4]}{i%8+1}号馈线","type":"计划停电" if planned else "故障停电","startTime":(NOW+timedelta(hours=i-12)).strftime("%Y-%m-%d %H:%M"),"expectedMinutes":60+(i%5)*30,"affectedUsers":12+i*17,"status":"已通知" if planned else "已恢复"})
    for i in range(12):
        HEAT.append({"area":f"{['北区','开发区','南区','东区'][i%4]}-{i+1}网","heatSource":plants[i%3],"supplyTempC":round(82+(i%5)*2.4,1),"returnTempC":round(44+(i%4)*2.1,1),"pressureMpa":round(.62+(i%5)*.05,2),"flowTph":420+i*73,"loadMW":round(58+i*8.7,1),"status":"温差关注" if i%6==0 else "稳定"})
        if i%4==0: HEAT_ALARMS.append({"alarmNo":f"HA-{40+i}","area":HEAT[-1]["area"],"type":["流量偏低","供温偏低","压差异常"][i%3],"value":70+i,"threshold":80,"startTime":(NOW-timedelta(minutes=20+i*7)).strftime("%Y-%m-%d %H:%M"),"handled":i%8!=0})
    for i in range(10): GAS.append({"station":f"{['开发区','北区','南区','城东'][i%4]}{['门站','调压站'][i%2]}{i+1}","dailySupply10kM3":round(12+i*3.7,1),"instantFlowM3h":6200+i*1260,"inletPressureMpa":round(.4+(i%4)*.31,2),"outletPressureMpa":round(.18+(i%3)*.07,2),"odorizerStatus":"需补充" if i==6 else "正常","status":"运行"})
    levels=["重大","较大","一般","低"]
    for i in range(27): RISKS.append({"riskNo":f"R-2026-{130+i}","site":(SUBSTATIONS+LINES+HEAT)[i%len(SUBSTATIONS+LINES+HEAT)].get("station") or (SUBSTATIONS+LINES+HEAT)[i%len(SUBSTATIONS+LINES+HEAT)].get("line") or (SUBSTATIONS+LINES+HEAT)[i%len(SUBSTATIONS+LINES+HEAT)].get("area"),"category":["设备重载","导线温升","热网异常","电气火灾","人员违章"][i%5],"level":levels[i%4],"owner":["输变电运维班","线路运检班","热网运行班","安全监察部"][i%4],"measure":"落实专项检查、在线监测和闭环整改","status":"已销号" if i%6==0 else "管控中"})

_expand_energy_demo()

def _filter(rows, keyword=""):
    return [r for r in rows if not keyword or keyword in " ".join(str(v) for v in r.values())]

@tool
def query_generation_units(keyword: str = "", status: str = "") -> str:
    """查询发电/热电联产机组运行、出力、煤耗和可用率。"""
    rows=_filter(UNITS,keyword); rows=[x for x in rows if not status or status in x["status"]]; return _rows(rows)
@tool
def query_power_generation_realtime(plant: str = "") -> str:
    """汇总实时发电出力、装机容量和供热负荷。"""
    rows=[x for x in UNITS if not plant or plant in x["plant"]]; return _d({"installedMW":sum(x["capacityMW"] for x in rows),"outputMW":round(sum(x["outputMW"] for x in rows),1),"heatLoadMW":round(sum(x["heatLoadMW"] for x in rows),1),"loadRate":round(sum(x["outputMW"] for x in rows)/sum(x["capacityMW"] for x in rows)*100,1),"asOf":NOW.strftime("%Y-%m-%d %H:%M")})
@tool
def summarize_grid_load() -> str:
    """汇总电网实时负荷、峰值、供电可靠性和新能源占比。"""
    return _d({"currentLoadMW":742.6,"dailyPeakMW":816.3,"dailyMinimumMW":536.8,"supplyReliabilityPct":99.982,"renewableSharePct":12.6,"frequencyHz":50.01,"asOf":NOW.strftime("%Y-%m-%d %H:%M")})
@tool
def query_substations(keyword: str = "", status: str = "") -> str:
    """查询变电站主变负荷、负载率、状态和未处理告警。"""
    rows=_filter(SUBSTATIONS,keyword); rows=[x for x in rows if not status or status in x["status"]]; return _rows(rows)
@tool
def query_line_operations(keyword: str = "", status: str = "") -> str:
    """查询输配电线路电流、负载率、温度和巡检状态。"""
    rows=_filter(LINES,keyword); rows=[x for x in rows if not status or status in x["status"]]; return _rows(rows)
@tool
def query_outage_events(keyword: str = "", event_type: str = "") -> str:
    """查询计划停电和故障停电事件、影响范围与恢复情况。"""
    rows=_filter(OUTAGES,keyword); rows=[x for x in rows if not event_type or event_type in x["type"]]; return _rows(rows)
@tool
def query_heat_supply(area: str = "") -> str:
    """查询供热温度、压力、流量、热负荷和运行状态。"""
    return _rows([x for x in HEAT if not area or area in x["area"]])
@tool
def query_heat_network_alarms(handled: str = "") -> str:
    """查询热网温压流异常、泄漏等报警。"""
    rows=HEAT_ALARMS
    if handled: rows=[x for x in rows if x["handled"]==(handled.lower() in {"true","1","yes","已处理"})]
    return _rows(rows)
@tool
def query_gas_supply(station: str = "") -> str:
    """查询天然气门站/调压站供气量、流量、压力与加臭状态。"""
    return _rows([x for x in GAS if not station or station in x["station"]])
@tool
def query_dispatch_commands(command_type: str = "", status: str = "") -> str:
    """查询电力、供热、燃气调度指令及执行闭环。"""
    return _rows([x for x in DISPATCH if (not command_type or command_type in x["type"]) and (not status or status in x["status"])])
@tool
def query_energy_consumption(metric: str = "综合") -> str:
    """查询供电煤耗、厂用电率、线损率、热损率和气损率等经营指标。"""
    return _d({"period":"本月","generation10kKWh":28640,"powerSales10kKWh":25470,"heatSales10kGJ":86.2,"gasSales10kM3":1048,"coalConsumptionGPerKWh":294.6,"auxPowerRatePct":6.8,"lineLossRatePct":4.21,"heatLossRatePct":8.7,"gasLossRatePct":1.36})
@tool
def query_energy_safety_risks(level: str = "", status: str = "") -> str:
    """查询电厂、电网、热网和燃气设施安全风险及管控措施。"""
    return _rows([x for x in RISKS if (not level or level in x["level"]) and (not status or status in x["status"])])
@tool
def summarize_energy_kpis() -> str:
    """生成电、热、气一体化运营驾驶舱核心指标。"""
    return _d({"power":{"outputMW":567.2,"gridLoadMW":742.6,"reliabilityPct":99.982},"heat":{"loadMW":368.3,"stableAreas":2,"alertAreas":1},"gas":{"dailySupply10kM3":60.0,"runningStations":2},"safety":{"activeRisks":3,"unhandledAlarms":2},"asOf":NOW.strftime("%Y-%m-%d %H:%M")})

ENERGY_TOOLS=[query_generation_units,query_power_generation_realtime,summarize_grid_load,query_substations,query_line_operations,query_outage_events,query_heat_supply,query_heat_network_alarms,query_gas_supply,query_dispatch_commands,query_energy_consumption,query_energy_safety_risks,summarize_energy_kpis]
