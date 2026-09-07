"""生成《智慧医院急诊绿通与高价值医疗资产智能运营中心》销售培训 PPT。

14页全景架构与实战销售指南，采用深色医疗科技风，包含完整讲师备注与量化销售话术。
"""

from __future__ import annotations

from pathlib import Path
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

OUTPUT = Path("/home/administrator/emergency-rfid-agent-demo/docs/智慧医院急诊绿通与医疗资产智能运营中心-销售培训.pptx")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

W, H = 13.333, 7.5

# 医疗科技与智能调度配色
BG = "0A121A"        # 深邃医疗科技底色
PANEL = "101D28"     # 卡片底色
PANEL_2 = "152735"   # 强调卡片底色
STEEL = "243948"     # 次级边框
LINE = "2D4556"      # 分割线
WHITE = "F1F5F8"     # 主文字白
MUTED = "94A7B4"     # 弱化提示文字
TEAL = "20C997"      # 生命绿 / 急救绿通 / 抢救成功率
CYAN = "3BC9DB"      # 物联感知 / 资产定位 / 设备状态
RED = "FA5252"       # 急诊红牌 / 超时预警 / 越界报警
YELLOW = "FCC419"    # 重点数值 / 关键价值 / 金牌话术
BLUE = "4DABF7"      # AI大脑 / 智能决策 / 质控统计
FONT = "Microsoft YaHei"


def rgb(value: str) -> RGBColor:
    return RGBColor.from_string(value)


def set_bg(slide, color: str = BG):
    bg = slide.background
    bg.fill.solid()
    bg.fill.fore_color.rgb = rgb(color)


def add_box(slide, x, y, w, h, fill=PANEL, line=LINE, radius=True, width=1):
    kind = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(fill)
    shape.line.color.rgb = rgb(line)
    shape.line.width = Pt(width)
    return shape


def add_text(slide, text, x, y, w, h, size=18, color=WHITE, bold=False,
             align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP, font=FONT, margin=0.02):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.margin_left = Inches(margin)
    frame.margin_right = Inches(margin)
    frame.margin_top = Inches(margin)
    frame.margin_bottom = Inches(margin)
    frame.vertical_anchor = valign
    p = frame.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = rgb(color)
    return box


def add_rich_lines(slide, lines, x, y, w, h, size=15, color=WHITE, bullet=False, spacing=8):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.margin_left = Inches(0.04)
    frame.margin_right = Inches(0.04)
    for index, item in enumerate(lines):
        if isinstance(item, tuple):
            text, item_color, bold = item
        else:
            text, item_color, bold = item, color, False
        p = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        p.text = ("•  " if bullet else "") + text
        p.font.name = FONT
        p.font.size = Pt(size)
        p.font.bold = bold
        p.font.color.rgb = rgb(item_color)
        p.space_after = Pt(spacing)
    return box


def add_title(slide, title: str, subtitle: str = "", index: int | None = None):
    add_box(slide, 0.45, 0.34, 0.08, 0.48, fill=TEAL, line=TEAL, radius=False, width=0)
    add_text(slide, title, 0.68, 0.27, 10.9, 0.5, size=24, bold=True)
    if subtitle:
        add_text(slide, subtitle, 0.7, 0.78, 11.7, 0.32, size=10.5, color=MUTED)
    if index is not None:
        add_text(slide, f"{index:02d}", 12.08, 0.3, 0.72, 0.35, size=12, color=TEAL, bold=True, align=PP_ALIGN.RIGHT)
    line = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(0.5), Inches(1.16), Inches(12.82), Inches(1.16))
    line.line.color.rgb = rgb(LINE)
    line.line.width = Pt(1)


def add_footer(slide, number: int):
    add_text(slide, "智慧医院：急诊绿通与高价值医疗资产智能运营中心｜销售培训课件", 0.52, 7.15, 6.8, 0.18, size=8.5, color="6F838E")
    add_text(slide, f"{number:02d}", 12.15, 7.12, 0.65, 0.2, size=8.5, color="6F838E", align=PP_ALIGN.RIGHT)


def add_notes(slide, text: str):
    try:
        slide.notes_slide.notes_text_frame.text = text
    except Exception:
        pass


def add_badge(slide, text, x, y, w, color=TEAL):
    add_box(slide, x, y, w, 0.34, fill=PANEL_2, line=color, radius=True, width=1)
    add_text(slide, text, x + 0.04, y + 0.04, w - 0.08, 0.22, size=9.5, color=color, bold=True, align=PP_ALIGN.CENTER)


def add_metric(slide, value, label, x, y, w, color=YELLOW):
    add_box(slide, x, y, w, 1.05, fill=PANEL, line=LINE)
    add_text(slide, value, x + 0.12, y + 0.12, w - 0.24, 0.42, size=24, color=color, bold=True)
    add_text(slide, label, x + 0.12, y + 0.58, w - 0.24, 0.28, size=10.5, color=MUTED)


def new_slide(prs, number, title, subtitle=""):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide)
    add_title(slide, title, subtitle, number)
    add_footer(slide, number)
    return slide


def build():
    prs = Presentation()
    prs.slide_width = Inches(W)
    prs.slide_height = Inches(H)
    prs.core_properties.title = "智慧医院急诊绿通与高价值医疗资产智能运营中心｜销售培训"
    prs.core_properties.subject = "面向三甲医院与急危重症救治中心的AI+IoT智能运营解决方案"
    prs.core_properties.author = "医疗智能运营中心团队"

    # =========================================================================
    # 01 封面
    # =========================================================================
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide)
    add_box(slide, 0, 0, 0.16, H, fill=TEAL, line=TEAL, radius=False, width=0)
    for i in range(8):
        line = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(5.0 + i), Inches(0), Inches(2.4 + i), Inches(7.5))
        line.line.color.rgb = rgb("132431")
        line.line.width = Pt(0.7)
    add_text(slide, "智慧医院急诊绿通与高价值资产", 0.85, 1.55, 10.5, 0.65, size=36, bold=True)
    add_text(slide, "智能运营中心 (Smart Emergency & Asset Agent)", 0.88, 2.35, 10.5, 0.52, size=24, color=TEAL, bold=True)
    add_text(slide, "连接患者、医护、高值装备与急救空间\n让急救争分夺秒，让资产透明高效", 0.9, 3.25, 9.5, 0.95, size=18, color="B5CCD8")
    add_box(slide, 0.9, 4.5, 11.2, 0.8, fill=PANEL, line=CYAN)
    add_text(slide, "聚焦医院急诊五大中心救治时效考核  ×  解决高价值移动医疗设备盘点与调度痛点", 1.15, 4.75, 10.7, 0.35, size=13.5, color=WHITE, bold=True)

    add_badge(slide, "医疗产品销售培训", 0.9, 5.7, 1.8, TEAL)
    add_badge(slide, "三甲医院攻坚版", 2.9, 5.7, 1.6, CYAN)
    add_badge(slide, "AI+物联双底座", 4.7, 5.7, 1.5, YELLOW)
    add_text(slide, "SMART HEALTHCARE EMERGENCY & ASSET INTELLIGENCE", 0.92, 6.75, 6.5, 0.25, size=9, color="5D7989")
    add_notes(slide, "开场引导：向客户介绍时，开篇要声明这绝不是单纯的硬件定位标签，也不是又一个难用的传统HIS插件，而是一套直接对齐三甲医院急危重症五大中心评审标准、解决急诊抢救延误与设备找不到两难困境的 AI 智能运营平台。")

    # =========================================================================
    # 02 行业痛点与客户机遇
    # =========================================================================
    slide = new_slide(prs, 2, "政策牵引与现场困境：急救与资产双重痛点", "医院不是缺少系统，而是缺少能够跨越物理时空、实时预警与调配的运营中枢")
    # 左侧急诊
    add_box(slide, 0.65, 1.45, 5.85, 4.5, fill=PANEL, line=RED)
    add_text(slide, "🚨 急救绿通痛点：时间就是生命，传统管理难闭环", 0.9, 1.68, 5.35, 0.35, size=14, color=RED, bold=True)
    emer_pains = [
        ("D-to-B/D-to-N考核达标难：", RED, True),
        ("胸痛急性心梗门球时间需<90分钟，卒中溶栓<60分钟，传统手工计时间漏洞百出，无法精准追溯环节延误。", WHITE, False),
        ("患者“推到哪里没人知道”：", RED, True),
        ("急诊绿通涉及分诊、抢救室、CT影像、介入室、手术室多科室协同，护士频繁打电话催问位置，协同成本高昂。", WHITE, False),
        ("超时滞留缺乏主动拦截预警：", RED, True),
        ("重症患者在检查环节超时滞留无自动警报，往往错失黄金抢救期，潜藏巨大医疗纠纷风险。", WHITE, False),
    ]
    add_rich_lines(slide, emer_pains, 0.9, 2.15, 5.35, 3.6, size=11, spacing=6)

    # 右侧资产
    add_box(slide, 6.85, 1.45, 5.85, 4.5, fill=PANEL, line=CYAN)
    add_text(slide, "🩺 医疗设备痛点：高值设备找寻难、闲置与短缺并存", 7.1, 1.68, 5.35, 0.35, size=14, color=CYAN, bold=True)
    asset_pains = [
        ("紧急抢救“找设备要半小时”：", CYAN, True),
        ("呼吸机、移动DR、除颤仪、注输泵经常跨科室借用，急救时常满楼跑找设备，耽误抢救。", WHITE, False),
        ("科室私自囤积，全院利用率低下：", CYAN, True),
        ("部分科室怕急用将公共设备“藏”在库房，设备真实开机率低，医院设备科盲目重复高价采购。", WHITE, False),
        ("设备越界流失、带病待机隐患：", CYAN, True),
        ("昂贵贵重设备推离指定院区难以防范，部分设备电池耗尽或离线未报，急救推上前才发现无法使用。", WHITE, False),
    ]
    add_rich_lines(slide, asset_pains, 7.1, 2.15, 5.35, 3.6, size=11, spacing=6)

    add_box(slide, 0.65, 6.12, 12.05, 0.65, fill=PANEL_2, line=YELLOW)
    add_text(slide, "核心销售切入点：以国家急危重症“五大中心”评审达标为抓手，以设备科盘点降本提效为支点", 0.9, 6.32, 11.5, 0.3, size=13.5, color=YELLOW, bold=True, align=PP_ALIGN.CENTER)
    add_notes(slide, "讲师重点：销售切忌一上去就跟客户讲RFID硬件技术细节，要直击医院核心痛点：副院长关心国家五大中心考核能不能过、医疗事故怎么防；急诊主任关心D-to-B时间能不能达标；设备科长关心几千万的设备到底有没有人在用。")

    # =========================================================================
    # 03 医院客户画像与决策链攻坚
    # =========================================================================
    slide = new_slide(prs, 3, "客户画像与决策链攻坚：找对人、说对话、解对题", "公立三甲与大型二甲医院决策链分析与各层级核心诉求")
    roles = [
        ("业务发起人", "急诊科主任 / 五大中心负责人", RED, [
            ("关注焦点：", RED, True),
            ("抢救成功率、通道超时报警、急诊滞留时间、医护与设备协同效率。", WHITE, False),
            ("攻坚话术：", YELLOW, True),
            ("“患者佩戴智能手环自动打卡各环节，超时红牌自动推给责任医生，D-to-B达标率直接达标提升。”", WHITE, False),
        ]),
        ("设备买单方", "医学工程处长 / 设备科长", CYAN, [
            ("关注焦点：", CYAN, True),
            ("全院高值设备台账、动态位置定位、开机利用率、闲置盘活与重复采购把关。", WHITE, False),
            ("攻坚话术：", YELLOW, True),
            ("“一秒查出全院呼吸机在哪里、哪台在待机闲置，盘点从3天缩短到10秒，年均避免上百万重复购置。”", WHITE, False),
        ]),
        ("技术把关人", "信息处长 / 信息科主任", BLUE, [
            ("关注焦点：", BLUE, True),
            ("系统集成复杂度、与HIS/PACS低耦合接口、数据院内私有化安全、服务器资源占用。", WHITE, False),
            ("攻坚话术：", YELLOW, True),
            ("“标准REST API与无侵入式集成，支持纯内网离线大模型与物联底座，不改现有HIS一行代码。”", WHITE, False),
        ]),
        ("终极决策者", "分管业务副院长 / 院长", TEAL, [
            ("关注焦点：", TEAL, True),
            ("国家三甲公立医院绩效国考加分、医疗纠纷秒级举证、高科技标杆示范、投资回报率ROI。", WHITE, False),
            ("攻坚话术：", YELLOW, True),
            ("“花极低代价补齐智慧急救与智慧管理两大短板，有实打实的五大中心质控报表与全生命周期台账。”", WHITE, False),
        ]),
    ]
    for i, (tag, title, color, lines) in enumerate(roles):
        x = 0.65 + i * 3.05
        add_box(slide, x, 1.45, 2.9, 4.5, fill=PANEL, line=color)
        add_badge(slide, tag, x + 0.2, 1.65, 1.3, color)
        add_text(slide, title, x + 0.2, 2.05, 2.5, 0.45, size=13.5, color=WHITE, bold=True)
        add_rich_lines(slide, lines, x + 0.2, 2.65, 2.5, 3.1, size=10.5, spacing=6)

    add_box(slide, 0.65, 6.12, 12.05, 0.65, fill=PANEL_2, line=LINE)
    add_text(slide, "销售实战原则：急诊科点火（制造紧迫需求） ➡️ 设备科跟进（提供预算渠道） ➡️ 院长定局", 0.9, 6.32, 11.5, 0.3, size=13, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    add_notes(slide, "讲师重点：销售最容易踩的坑是只找信息科。信息科是防守型部门，只找信息科往往会因为排期拖半年。最佳路径是从急诊科主任或设备科长切入，形成业务刚需后由业务部门向信息科提交立项。")

    # =========================================================================
    # 04 产品全景架构：1 + 2 + 4 + N
    # =========================================================================
    slide = new_slide(prs, 4, "产品全景架构：1 + 2 + 4 + N 赋能体系", "标准模块化设计，统一产品内核，按客户医院急诊与资产场景随需组合")
    blocks = [
        ("1", "一个智能运营中心", "全院急救与资产全景大屏\n统一调度驾驶舱与态势监测", TEAL, 0.65, 2.85),
        ("2", "两大核心支撑底座", "医疗多源物联网感知底座 (RFID/BLE/UWB)\nLangGraph 医疗垂直智能体大脑", CYAN, 3.7, 2.85),
        ("4", "四大专业业务闭环", "急救绿通闭环 ｜ 资产全息盘点\n设备能效研判 ｜ 全息空间地图", YELLOW, 6.75, 2.85),
        ("N", "多种场景交付入口", "护士站大屏 ｜ 医生工作站\n移动端PDA ｜ 企微/Telegram 机器人", BLUE, 9.8, 2.85),
    ]
    for num, title, desc, color, x, w in blocks:
        add_box(slide, x, 1.5, w, 4.3, fill=PANEL, line=color)
        add_text(slide, num, x + 0.2, 1.85, w - 0.4, 0.85, size=48, color=color, bold=True, align=PP_ALIGN.CENTER)
        add_text(slide, title, x + 0.15, 2.95, w - 0.3, 0.4, size=16, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
        add_text(slide, desc, x + 0.2, 3.65, w - 0.4, 1.8, size=12, color=MUTED, align=PP_ALIGN.CENTER)

    add_box(slide, 0.65, 6.0, 12.0, 0.75, fill=PANEL_2, line=TEAL)
    add_text(slide, "核心技术优势：非传统统计看板，而是具备自学习、工具自路由与智能反思的 LangGraph 智能体", 0.9, 6.25, 11.5, 0.3, size=13.5, color=TEAL, bold=True, align=PP_ALIGN.CENTER)
    add_notes(slide, "一张图让客户记牢架构：1个中心管全盘，2个底座（物联硬件不绑定，AI大脑是自主知识产权），4大场景即插即用，N个终端随时随地查数。")

    # =========================================================================
    # 05 核心业务一：急诊绿通全时空闭环
    # =========================================================================
    slide = new_slide(prs, 5, "急诊绿通业务闭环：全自动节点打卡与超时预警", "彻底终结纸质登记时代，全流程打通胸痛、卒中、创伤、危重孕产与儿科通道")
    # 左侧流程
    flow_steps = [
        ("01 急救患者入院", "佩戴智能定位手环，关联门诊号与通道类型", TEAL),
        ("02 抢救分诊打卡", "自动识别分诊台进入与停留时长，启动SLA计时", CYAN),
        ("03 医技影像检查", "进入CT/DR室无感记录时间，超时自动触发黄牌催办", YELLOW),
        ("04 专科介入手术", "介入导管室/急诊手术室进入记录，闭环D-to-B全程", BLUE),
        ("05 救治归档复盘", "一键导出抢救轨迹与耗时日志，满足五大中心评审", WHITE),
    ]
    for i, (title, desc, color) in enumerate(flow_steps):
        y = 1.45 + i * 0.9
        add_box(slide, 0.65, y, 6.2, 0.76, fill=PANEL, line=color)
        add_text(slide, title, 0.85, y + 0.16, 1.8, 0.3, size=13, color=color, bold=True)
        add_text(slide, desc, 2.7, y + 0.17, 4.0, 0.45, size=10.5, color=WHITE)

    # 右侧核心能力
    add_box(slide, 7.1, 1.45, 5.55, 4.35, fill=PANEL_2, line=RED)
    add_text(slide, "⚠️ 超时红黄牌机制：防范纠纷的护城河", 7.35, 1.7, 5.0, 0.35, size=15, color=RED, bold=True)
    rich = [
        ("分诊超时监测：", YELLOW, True),
        ("患者挂号后超过15分钟未进入抢救室或诊室，系统主动通知分诊护士。", WHITE, False),
        ("CT/影像滞留警报：", YELLOW, True),
        ("急诊绿通患者在影像区滞留超过20分钟，红牌告警同步推送至急诊值班主任。", WHITE, False),
        ("客观时空举证：", TEAL, True),
        ("精准记录每个科室、每间检查室的停留分钟数，出现纠纷秒级调取客观时间线，厘清责任。", WHITE, False),
        ("自动生成绿通质控表：", CYAN, True),
        ("无需人工月底加班统计，自动生成胸痛中心门球时间（D-to-B）与卒中门溶时间（D-to-N）月度报表。", WHITE, False),
    ]
    add_rich_lines(slide, rich, 7.35, 2.2, 5.05, 3.4, size=11, spacing=7)

    add_box(slide, 0.65, 6.05, 12.0, 0.7, fill=PANEL, line=LINE)
    add_text(slide, "实测数据标杆：绿通患者全流程转运时间缩短 28%，国家中心评审质控数据填报效率提升 90%", 0.9, 6.28, 11.5, 0.3, size=13, color=TEAL, bold=True, align=PP_ALIGN.CENTER)
    add_notes(slide, "讲师重点：医院急诊主任最头疼的事情之一就是“月底补数据应付国家中心检查”，耗费大量医护精力且真实性堪忧。我们这套系统可以让数据在救治过程中全自动产生，主任听了眼睛一定会亮。")

    # =========================================================================
    # 06 核心业务二：高价值医疗资产秒级定位与全院调配
    # =========================================================================
    slide = new_slide(prs, 6, "高价值医疗资产：秒级找寻、防丢越界与跨区调配", "解决抢救时找不到设备、科室借调扯皮、贵重资产离线越界的三大顽疾")
    cards = [
        ("01", "10秒极速寻机", CYAN, "告别“满楼跑找呼吸机”", [
            ("房间级精细定位：", CYAN, True),
            ("为呼吸机、监护仪、移动DR、除颤仪贴附微型防拆定位标签，在地图上直观显示位于几楼、哪个床位。", WHITE, False),
            ("自然语言一键查找：", WHITE, True),
            ("在手机或工作站直接问“输液泵12号在哪”，立即返回具体科室、当前床位及状态。", WHITE, False),
        ]),
        ("02", "跨科室借调闭环", TEAL, "终结科室借用不还扯皮", [
            ("进出区域自动记录：", TEAL, True),
            ("设备从抢救室被借调至ICU或手术室，系统自动生成进出记录与转运台账。", WHITE, False),
            ("动态责任人追溯：", WHITE, True),
            ("明确当前设备在借科室与流转时长，月度自动结算设备跨科室使用频次。", WHITE, False),
        ]),
        ("03", "电子围栏越界报警", RED, "贵重资产防盗防丢防移出", [
            ("划定专属安全边界：", RED, True),
            ("为院属特种设备划定楼层或科室围栏，推离急诊大楼立即发出声光与手机报警。", WHITE, False),
            ("防拆卸与离线预警：", WHITE, True),
            ("标签被恶意拆卸或电池电量低于10%时自动告警，杜绝急救推上去才发现没电。", WHITE, False),
        ]),
    ]
    for i, (idx, title, color, subtitle, items) in enumerate(cards):
        x = 0.65 + i * 4.05
        add_box(slide, x, 1.45, 3.9, 4.4, fill=PANEL, line=color)
        add_box(slide, x + 0.2, 1.7, 0.45, 0.45, fill=color, line=color, radius=True)
        add_text(slide, idx, x + 0.2, 1.75, 0.45, 0.35, size=14, color=BG, bold=True, align=PP_ALIGN.CENTER)
        add_text(slide, title, x + 0.78, 1.7, 2.9, 0.4, size=16, color=color, bold=True)
        add_text(slide, subtitle, x + 0.22, 2.25, 3.4, 0.35, size=11, color=MUTED)
        add_rich_lines(slide, items, x + 0.22, 2.75, 3.45, 2.9, size=10.5, spacing=7)

    add_box(slide, 0.65, 6.05, 12.0, 0.7, fill=PANEL_2, line=YELLOW)
    add_text(slide, "设备科采购痛点：医院每年买很多注输泵和监护仪，实际上30%在科室闲置，我们帮医院“盘活存量、精简增量”", 0.9, 6.28, 11.5, 0.3, size=12.5, color=YELLOW, bold=True, align=PP_ALIGN.CENTER)
    add_notes(slide, "讲师重点：对于医学工程处（设备科），设备丢失和盲目采购是科长背负的重大KPI压力。这套系统可以提供铁证如山的资产利用数据，帮助科长在院务会上科学把关采购。")

    # =========================================================================
    # 07 核心业务三：设备能效、闲置研判与智能决策
    # =========================================================================
    slide = new_slide(prs, 7, "设备能效与运营分析：用数据管资产、杜绝重复采购", "结合设备用电状态、使用时长与开机率，打造医院高价值资产的运营驾驶舱")
    metrics = [
        ("68.2%", "抢救室设备综合使用率", TEAL, 0.65),
        ("34.6%", "观察室部分设备闲置率(偏高)", RED, 3.7),
        ("10 秒", "全院高值设备一键盘点耗时", YELLOW, 6.75),
        ("0 发生", "重点监护资产离线越界失联", CYAN, 9.8),
    ]
    for val, label, color, x in metrics:
        add_metric(slide, val, label, x, 1.45, 2.85, color)

    # 下方左右对比
    add_box(slide, 0.65, 2.75, 5.85, 3.1, fill=PANEL, line=CYAN)
    add_text(slide, "📊 全生命周期能效与工时画像", 0.9, 2.95, 5.3, 0.35, size=14, color=CYAN, bold=True)
    left_items = [
        ("多维状态识别：", CYAN, True),
        ("精准采集设备“运行、待机、闲置、关机、离线”五种状态，统计真实治疗时间。", WHITE, False),
        ("科室利用率排行榜：", WHITE, True),
        ("横向对比急诊抢救室、EICU、观察室同类设备的开机率，为科室间统筹调配提供决策支持。", WHITE, False),
        ("维保校准智能提醒：", WHITE, True),
        ("累计运行满额时自动提醒设备科预防性检修，杜绝急救时设备故障卡壳。", WHITE, False),
    ]
    add_rich_lines(slide, left_items, 0.9, 3.4, 5.35, 2.3, size=11, spacing=7)

    add_box(slide, 6.85, 2.75, 5.85, 3.1, fill=PANEL, line=YELLOW)
    add_text(slide, "💰 医院采购降本的“尚方宝剑”", 7.1, 2.95, 5.3, 0.35, size=14, color=YELLOW, bold=True)
    right_items = [
        ("科室申请添置前先查存量：", YELLOW, True),
        ("某科室申请新购5台呼吸机时，系统一键调出全院该型号呼吸机当前空闲分布。", WHITE, False),
        ("推动急救设备资源池化共享：", WHITE, True),
        ("建立急救设备共享中心，用“分时借调”代替“各科室私买私存”，采购资金节省数百万元。", WHITE, False),
        ("公立医院国考支撑：", WHITE, True),
        ("直接输出国家卫健委要求的大型医用设备使用率指标与精细化管理报告。", WHITE, False),
    ]
    add_rich_lines(slide, right_items, 7.1, 3.4, 5.35, 2.3, size=11, spacing=7)

    add_box(slide, 0.65, 6.05, 12.0, 0.7, fill=PANEL_2, line=LINE)
    add_text(slide, "商业价值总结：一套系统既解决了急诊医护的急用之困，又帮设备科长和副院长省下了真金白银", 0.9, 6.28, 11.5, 0.3, size=13, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    add_notes(slide, "讲师重点：销售要学会算账。一台高端呼吸机30~50万，一台移动DR上百万。医院通过我们的平台将设备综合利用率提升30%，相当于少采购几台设备，直接收回整个软件和硬件的投资成本。")

    # =========================================================================
    # 08 核心业务四：全景时空数字地图与 3D 可视化
    # =========================================================================
    slide = new_slide(prs, 8, "全景时空数字地图：院内平面与立体的孪生可视化", "直观掌控全院急危重症患者流转与重要医疗装备热力分布")
    map_features = [
        ("多楼层楼面全息俯瞰", "分层清晰呈现 1F急诊大厅/抢救室/CT室、2F介入/ICU、3F手术室、4F重症监护", TEAL),
        ("人车物全要素同屏呈现", "不同颜色与图标区分医生、护士、患者、呼吸机、监护仪、病床，位置动态刷新", CYAN),
        ("红黄牌报警联动闪烁", "发生超时滞留、越界推离、设备离线时，地图对应点位闪烁预警并弹出处置卡片", RED),
        ("历史轨迹时空回放", "拉动时间轴即可重现某位患者或某台设备的院内完整移动路线与停留节点", BLUE),
    ]
    for i, (title, desc, color) in enumerate(map_features):
        x = 0.65 + i * 3.05
        add_box(slide, x, 1.45, 2.9, 4.3, fill=PANEL, line=color)
        add_text(slide, f"0{i+1}", x + 0.2, 1.7, 2.5, 0.4, size=22, color=color, bold=True)
        add_text(slide, title, x + 0.2, 2.2, 2.5, 0.5, size=15, color=WHITE, bold=True)
        add_text(slide, desc, x + 0.2, 2.85, 2.5, 2.6, size=11, color=MUTED)

    add_box(slide, 0.65, 6.0, 12.0, 0.8, fill=PANEL_2, line=TEAL)
    add_text(slide, "极佳的演示效果：领导参观与指挥中心大屏的最佳展示窗口，支持 2D 平面图与 3D 数字孪生模式自由切换", 0.9, 6.25, 11.5, 0.3, size=13, color=TEAL, bold=True, align=PP_ALIGN.CENTER)
    add_notes(slide, "讲师重点：销售在打动客户领导层时，数字地图是视觉效果最好的杀手锏。院领导一眼就能看懂全院当前有多少绿通患者、哪台设备在哪个房间。在方案交流中务必重点投屏演示这一模块。")

    # =========================================================================
    # 09 差异化壁垒：AI 智能体人机交互新范式
    # =========================================================================
    slide = new_slide(prs, 9, "差异化护城河：AI 智能体让医疗数据“开口说话”", "拒绝传统难操作的死板系统；支持自然语言问答、自动生成报表、图表与原理图")
    # 左侧对话示例
    add_box(slide, 0.65, 1.45, 5.85, 4.4, fill=PANEL, line=BLUE)
    add_text(slide, "💬 医护人员与院领导的自然语言交互", 0.9, 1.68, 5.35, 0.35, size=14, color=BLUE, bold=True)
    chats = [
        ("问：“抢救室现在空闲的呼吸机是哪台？”", YELLOW, True),
        ("答：「经查询，EICU-2床的呼吸机3号当前处于待机状态，电量充足，可立即调拨。」", WHITE, False),
        ("问：“今天有哪些绿通患者检查超时？”", RED, True),
        ("答：「发现1例超时：胸痛患者张三在CT室已停留35分钟（阈值20分钟），已发黄牌提示。」", WHITE, False),
        ("问：“画一张急诊科人员与设备分布架构图”", CYAN, True),
        ("答：智能体自动调用出图模型，直接返回清新专业的 2D 科普原理插画与架构图。", WHITE, False),
    ]
    add_rich_lines(slide, chats, 0.9, 2.15, 5.35, 3.5, size=11, spacing=7)

    # 右侧技术底色
    add_box(slide, 6.85, 1.45, 5.85, 4.4, fill=PANEL_2, line=TEAL)
    add_text(slide, "🧠 为什么医院信赖我们的 Agent 架构？", 7.1, 1.68, 5.35, 0.35, size=14, color=TEAL, bold=True)
    agent_strengths = [
        ("数字全部来自真实物联接口：", TEAL, True),
        ("模型只做理解、工具路由与渲染输出，严禁猜测臆造数字，杜绝大模型“幻觉”误导医疗救治。", WHITE, False),
        ("支持纯内网离线大模型运行：", CYAN, True),
        ("适配本地 Qwen / 本地模型框架，医院敏感患者健康与轨迹数据 100% 不出院，符合等级保护三级。", WHITE, False),
        ("自动输出多样化结果：", YELLOW, True),
        ("根据问题自动匹配 Markdown 表格、柱状图、饼图、仪表盘或平面地图，无需人工繁琐导出排版。", WHITE, False),
    ]
    add_rich_lines(slide, agent_strengths, 7.1, 2.15, 5.35, 3.5, size=11, spacing=7)

    add_box(slide, 0.65, 6.05, 12.0, 0.7, fill=PANEL, line=LINE)
    add_text(slide, "一句话产品优势：它既是一个24小时不疲倦的急诊质控管家，也是一个随叫随到的设备科调度秘书", 0.9, 6.28, 11.5, 0.3, size=13, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    add_notes(slide, "讲师重点：向医院信息科强调：大模型不是在胡乱自由生成，而是由 LangGraph ReAct 严格调控工具调用。模型不能编造床位、患者或设备位置，所有回答必须锚定在底层数据库上。这一特性能打消医疗客户对大模型安全性的疑虑。")

    # =========================================================================
    # 10 竞品对比与核心竞争护城河
    # =========================================================================
    slide = new_slide(prs, 10, "竞品对比与核心护城河：四大维度形成代际碾压", "对比传统纯硬件厂商、传统HIS外挂模块、孤岛式定位软件")
    add_box(slide, 0.65, 1.45, 12.0, 4.4, fill=PANEL, line=LINE)
    headers = ["评估维度", "传统RFID纯硬件方案", "传统HIS/PACS外挂模块", "本运营中心 (AI Agent+IoT)"]
    x_offsets = [0.85, 2.7, 5.9, 9.3]
    widths = [1.7, 3.0, 3.2, 3.1]
    for h_idx, (h_title, h_x, h_w) in enumerate(zip(headers, x_offsets, widths)):
        c = TEAL if h_idx == 3 else WHITE
        add_text(slide, h_title, h_x, 1.65, h_w, 0.35, size=13, color=c, bold=True)
    line = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(0.85), Inches(2.05), Inches(12.45), Inches(2.05))
    line.line.color.rgb = rgb(LINE); line.line.width = Pt(1)

    rows = [
        ("数据深度与定位能力", "只给坐标冷数据，无法关联患者病案与流程", "依赖人工点击HIS录入，无实时物理位置感知", "时空坐标与救治流程深度融合，全自动无感打卡"),
        ("告警与业务闭环", "只有简单的设备断开告警，无临床超时提醒", "被动记录事后数据，无法实时截断滞留延误", "急诊全流程超时红黄牌主动推送到人，闭环处置"),
        ("使用门槛与交互", "界面复杂，需要专业工程师在后台看点位", "菜单层级极深，医生忙于抢救根本没空点", "随时自然语言对话：“问一句话，3秒出全图”"),
        ("部署与系统耦合", "昂贵定制私有基站，换厂家推倒重来", "强依赖HIS大版本改造，费用昂贵排期半年", "物联硬件无关设计，标准API轻量集成，1周上线"),
    ]
    for r_idx, (dim, comp1, comp2, us) in enumerate(rows):
        y = 2.2 + r_idx * 0.88
        add_text(slide, dim, 0.85, y, 1.7, 0.6, size=11, color=CYAN, bold=True)
        add_text(slide, comp1, 2.7, y, 3.0, 0.7, size=10, color=MUTED)
        add_text(slide, comp2, 5.9, y, 3.2, 0.7, size=10, color=MUTED)
        add_text(slide, us, 9.3, y, 3.1, 0.7, size=10.5, color=TEAL, bold=True)

    add_box(slide, 0.65, 6.05, 12.0, 0.7, fill=PANEL_2, line=TEAL)
    add_text(slide, "核心护城河：硬件无关性（不绑架医院硬件资产） + 70+开箱即用临床与资产专用Skill", 0.9, 6.28, 11.5, 0.3, size=13, color=TEAL, bold=True, align=PP_ALIGN.CENTER)
    add_notes(slide, "讲师重点：医院最讨厌被单一硬件厂商绑架。我们的平台是“软件定义物联”，医院原先如果有蓝牙、RFID或Wi-Fi定位硬件，我们可以直接复用其坐标数据，帮客户盘活历史硬件资产，降低采购门槛。")

    # =========================================================================
    # 11 客户量化 ROI 与投资回报标尺
    # =========================================================================
    slide = new_slide(prs, 11, "客户量化 ROI：临床效益、管理效益与经济账", "向分管院长与财务处长汇报时，拿出无可辩驳的数据收益模型")
    roi_cards = [
        ("医疗质量与安全效益", RED, [
            ("急救时间压缩 25%~35%：", RED, True),
            ("急性心梗D-to-B、脑梗D-to-N平均缩短15-25分钟，挽救心肌与脑细胞，提高救治成功率。", WHITE, False),
            ("五大中心评审 100% 达标：", WHITE, True),
            ("质控指标由系统自动提取，杜绝人工造假被专家否决的风险，为医院三甲复审稳固拿分。", WHITE, False),
            ("医疗纠纷化解率大幅提升：", WHITE, True),
            ("客观秒级救治时空日志，谁的责任一目了然，避免不必要的赔偿与声誉受损。", WHITE, False),
        ]),
        ("医护工作减负效益", CYAN, [
            ("免去人工填表登记：", CYAN, True),
            ("急诊护士无需在危重患者推入时手动抄录各节点时间，每日人均节省机械劳动1.2小时。", WHITE, False),
            ("抢救找设备从半小时缩至秒级：", WHITE, True),
            ("医生一句话语音或文字查询，立即得知离自己最近的空闲呼吸机和除颤仪，抢救更从容。", WHITE, False),
            ("交接班智能汇总：", WHITE, True),
            ("交班时一键生成当班患者流转分布与设备报警处置单，交接更严密无缝。", WHITE, False),
        ]),
        ("医院直接经济效益", YELLOW, [
            ("高值设备采购年均节省上百万：", YELLOW, True),
            ("盘活全院各科室闲置设备，综合利用率提升35%~45%，避免同类高危设备盲目过度采购。", WHITE, False),
            ("资产盘点效率提升 95%：", WHITE, True),
            ("原来设备科需要全院逐个科室耗时数天盘点，现在系统后台“一键盘点”只需10秒生成。", WHITE, False),
            ("彻底防止资产外流遗失：", WHITE, True),
            ("电子围栏全天候值守，杜绝数万乃至数十万昂贵设备流失在院外。", WHITE, False),
        ]),
    ]
    for i, (title, color, items) in enumerate(roi_cards):
        x = 0.65 + i * 4.05
        add_box(slide, x, 1.45, 3.9, 4.4, fill=PANEL, line=color)
        add_text(slide, title, x + 0.22, 1.7, 3.45, 0.4, size=15, color=color, bold=True)
        line = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x + 0.22), Inches(2.15), Inches(x + 3.65), Inches(2.15))
        line.line.color.rgb = rgb(LINE); line.line.width = Pt(0.8)
        add_rich_lines(slide, items, x + 0.22, 2.3, 3.45, 3.4, size=10.5, spacing=7)

    add_box(slide, 0.65, 6.05, 12.0, 0.7, fill=PANEL_2, line=YELLOW)
    add_text(slide, "投资回收期测算：通常一家500张床位以上的综合医院，通过闲置设备盘活与管理增效，8~12 个月即可收回全部投资成本", 0.9, 6.28, 11.5, 0.3, size=12.5, color=YELLOW, bold=True, align=PP_ALIGN.CENTER)
    add_notes(slide, "讲师重点：销售跟院长谈ROI时，必须打“经济牌”加“声誉牌”。既有国家五大中心评审达标的政治声誉，又有设备科少买两台呼吸机直接省下上百万元的直接经济账。")

    # =========================================================================
    # 12 销售全流程攻坚与 POC 落地法
    # =========================================================================
    slide = new_slide(prs, 12, "销售全流程实战攻坚与 1周极速 POC 法", "如何打消客户疑虑，通过“小切口试用”快速锁定预算并推动招投标")
    stages = [
        ("第一阶段：痛点破冰", "以胸痛/卒中中心国家质控评审或急救设备找寻为切入点，拜访急诊主任和设备科长，做5分钟手机机器人互动演示", CYAN),
        ("第二阶段：高层方案交流", "面向分管业务副院长投屏演示全景数字地图、超时红黄牌机制与设备利用率报表，争取院领导口头支持与指示", TEAL),
        ("第三阶段：1周现场极速POC", "在抢救室与CT室两个关键节点部署少量轻量接收终端，绑定10位患者手环与20台急救设备，现场实测验证闭环", YELLOW),
        ("第四阶段：立项与标讯挂网", "以“急救绿通时空闭环与智慧资产运营”联合医务处、设备科立项，提供标准技术参数与招标方案，顺利落地", BLUE),
    ]
    for i, (title, desc, color) in enumerate(stages):
        y = 1.45 + i * 1.05
        add_box(slide, 0.65, y, 12.0, 0.9, fill=PANEL, line=color)
        add_box(slide, 0.85, y + 0.18, 0.55, 0.55, fill=color, line=color, radius=True)
        add_text(slide, str(i + 1), 0.85, y + 0.25, 0.55, 0.4, size=16, color=BG, bold=True, align=PP_ALIGN.CENTER)
        add_text(slide, title, 1.55, y + 0.2, 2.8, 0.35, size=14, color=color, bold=True)
        add_text(slide, desc, 4.35, y + 0.2, 8.1, 0.55, size=11, color=WHITE)

    add_box(slide, 0.65, 5.95, 12.0, 0.8, fill=PANEL_2, line=YELLOW)
    add_text(slide, "POC 成功关键秘诀：只验证最痛的两个闭环（患者CT检查超时自动报警 + 移动DR一键秒级定位），1周出数据报告即可锁标", 0.9, 6.2, 11.5, 0.3, size=12.5, color=YELLOW, bold=True, align=PP_ALIGN.CENTER)
    add_notes(slide, "讲师重点：销售最容易犯的错误是POC摊子铺得太大，想一次做全院。一定要“切口小、见效快”。挑急诊科最痛苦的一个检查室（比如CT室）和最常被抢调的20台设备，一周就能把震撼的数据对比摆在院长面前。")

    # =========================================================================
    # 13 经典异议应对与金牌话术宝典
    # =========================================================================
    slide = new_slide(prs, 13, "客户常见疑虑与金牌应对策略", "面对医院信息科、急诊主任与设备科长的经典刁钻异议")
    objections = [
        ("异议一：“我们已经上了HIS、EMR和移动护理系统，不需要重复建设”", [
            ("应对策略：", CYAN, True),
            ("明确“互补增强”而非替代定位。HIS是纯电子病历表单，不具备物理时空感知能力。", WHITE, False),
            ("标准金牌话术：", YELLOW, True),
            ("“主任您看，HIS知道患者开了CT单，但不知道患者到底有没有推到CT室门口、在里面等了多久。我们是给医院既有系统装上‘时空之眼’和‘预警雷达’，让HIS的数据真正鲜活起来。”", WHITE, False),
        ]),
        ("异议二：“急诊医生护士抢救争分夺秒，根本没时间配合扫码或操作复杂界面”", [
            ("应对策略：", TEAL, True),
            ("突出“全无感物联感知”与“微信/语音自然语言秒查”。", WHITE, False),
            ("标准金牌话术：", YELLOW, True),
            ("“护士完全不需要额外点电脑扫码，患者戴上手环推过去就自动完成打卡。找设备甚至不用开电脑，在手机企业微信里语音问一句‘移动呼吸机在哪’，直接返回床位号。”", WHITE, False),
        ]),
        ("异议三：“医院网络安全等级保护要求极严，医疗与患者数据绝对不能上公网云端”", [
            ("应对策略：", BLUE, True),
            ("强调100%全栈本地化私有部署、内网离线大模型运行机制。", WHITE, False),
            ("标准金牌话术：", YELLOW, True),
            ("“我们全面支持医院机房本地私有化部署。AI大模型采用本地量化部署方案，数据全部驻留在医院内网，零外网依赖，完全符合国家医疗信息安全等保三级规范。”", WHITE, False),
        ]),
    ]
    for i, (title, items) in enumerate(objections):
        y = 1.45 + i * 1.45
        add_box(slide, 0.65, y, 12.0, 1.32, fill=PANEL, line=LINE)
        add_text(slide, title, 0.85, y + 0.14, 11.5, 0.32, size=13, color=WHITE, bold=True)
        add_rich_lines(slide, items, 0.85, y + 0.48, 11.6, 0.76, size=10.5, spacing=4)

    add_box(slide, 0.65, 6.05, 12.0, 0.7, fill=PANEL_2, line=LINE)
    add_text(slide, "销售心法：永远不要去否定客户已有的信息化资产，而要帮客户现有资产“赋能增值、查漏补缺”", 0.9, 6.28, 11.5, 0.3, size=13, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    add_notes(slide, "讲师重点：销售要学会顺水推舟。客户说“我们系统很多了”，不要反驳，直接赞扬客户信息化建设基础好，正因为基础好，才具备升级“实时时空感知”与“智能体调度”的成熟土壤。")

    # =========================================================================
    # 14 销售实战行动清单与落地工具包
    # =========================================================================
    slide = new_slide(prs, 14, "销售实战行动清单：从今天起开始打单！", "销售团队必备武器库、初访五连问与第一阶段目标拆解")
    # 左侧武器库
    add_box(slide, 0.65, 1.45, 5.85, 4.3, fill=PANEL, line=TEAL)
    add_text(slide, "🧰 销售随身“武器库”清单", 0.9, 1.68, 5.35, 0.35, size=14, color=TEAL, bold=True)
    tools_list = [
        ("演示沙箱账号：", TEAL, True),
        ("随时可用的 PC 网页端与手机 Telegram/企业微信机器人（内置急诊绿通与设备数据）。", WHITE, False),
        ("五大中心质控对照表：", WHITE, True),
        ("一份详尽的国家五大中心标准与本系统打卡采集字段逐条对应表，见主任必备。", WHITE, False),
        ("设备科 ROI 测算计算器：", YELLOW, True),
        ("根据医院床位数与高值设备台数，3分钟生成全院设备利用率提升与采购节省金额测算单。", WHITE, False),
        ("典型三甲医院标杆方案白皮书：", CYAN, True),
        ("包含机房拓扑、网络接入、软硬件配置清单与标准招标文件模板。", WHITE, False),
    ]
    add_rich_lines(slide, tools_list, 0.9, 2.15, 5.35, 3.4, size=11, spacing=7)

    # 右侧行动准则
    add_box(slide, 6.85, 1.45, 5.85, 4.3, fill=PANEL_2, line=YELLOW)
    add_text(slide, "🎯 客户初访“黄金五连问”", 7.1, 1.68, 5.35, 0.35, size=14, color=YELLOW, bold=True)
    questions = [
        ("1. 问评审：", YELLOW, True),
        ("“主任，咱们医院今年胸痛或卒中中心国家质控复审，D-to-B时间达标有压力吗？”", WHITE, False),
        ("2. 问转运：", YELLOW, True),
        ("“急诊患者推去CT或急救时，医生怎么实时知道患者推到哪了？经常打电话吗？”", WHITE, False),
        ("3. 问找寻：", YELLOW, True),
        ("“大抢救或者夜班借用设备时，护士找一台呼吸机通常需要找多久？”", WHITE, False),
        ("4. 问闲置：", YELLOW, True),
        ("“科长，咱们医院注输泵和监护仪各科室实际开机率有准数吗？盲目采购多不多？”", WHITE, False),
        ("5. 问意向：", TEAL, True),
        ("“如果不用改动HIS，1周时间在抢救室免费试点验证效果，咱们主任愿意试试吗？”", WHITE, False),
    ]
    add_rich_lines(slide, questions, 7.1, 2.15, 5.35, 3.4, size=10.5, spacing=5)

    add_box(slide, 0.65, 5.95, 12.0, 0.8, fill=PANEL, line=TEAL)
    add_text(slide, "立即行动：用极简 5 分钟手机演示破冰，锁定客户急危重症评审痛点，开启第一批试点医院破局！", 0.9, 6.2, 11.5, 0.3, size=13.5, color=TEAL, bold=True, align=PP_ALIGN.CENTER)
    add_notes(slide, "总结收尾：每位销售培训后必须通过5分钟手机端演示通关考核。记住：销售卖的不是代码或标签，而是副院长放心睡好觉的急救安全感、急诊主任轻松通过国家中心考评的底气、以及设备科长科学管好上亿医院资产的专业工具。")

    prs.save(str(OUTPUT))
    print(f"✅ 成功生成销售培训 PPT：{OUTPUT}")
    print(f"   幻灯片总数：{len(prs.slides)} 张")


if __name__ == "__main__":
    build()
