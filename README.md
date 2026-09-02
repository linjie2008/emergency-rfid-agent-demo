# 急诊绿通 RFID 智能体 Demo

按《急诊绿通进出记录接口文档》做的最小对话 Demo：用 LangGraph 调 `getInOutMergeList` 同类数据，回答患者在哪、轨迹、停留时长、抢救室超时。

默认走本地 mock，不连业务系统。字段与真实接口一致，配上 `RFID_API_BASE` 即可切真实环境。

## 样例数据

约 **47 名患者**（今天 37 + 昨天 10），覆盖胸痛/卒中/创伤/孕产妇/儿科绿通。核心 5 人不变：

| 姓名 | 门诊号 | 腕带 EPC | 通道 | 当前 |
|------|--------|----------|------|------|
| 张三 | MZ20260608001 | E200001234560001 | 胸痛绿通 | 介入室 |
| 李四 | MZ20260608002 | E200001234560002 | 卒中绿通 | 卒中单元 |
| 王五 | MZ20260608003 | E200001234560003 | 创伤绿通 | 抢救室（滞留） |
| 赵六 | MZ20260608004 | E200001234560004 | 急诊绿通 | 分诊台 |
| 陈七 | MZ20260608005 | E200001234560005 | 急诊绿通 | 已离院 |

另外可问：现在 CT 室有谁、今天胸痛绿通几人、还有谁抢救室超时、昨天卒中绿通。

图表工具：在对话中说“生成柱状图/饼图/折线图”，智能体会在查询数据后调用 `create_chart`，前端直接渲染科技医疗风格图表，并支持下载 PNG。支持柱状图、饼图、折线图。

院内位置图：说“在地图上显示张三的位置”或“用平面图显示输液泵12号”，智能体会调用 `show_location_map`，按楼层渲染院内区域并高亮患者或设备当前位置。
也支持多人/多设备聚合，例如“显示所有患者实时位置”“显示抢救室所有患者”“显示所有设备分布”；同一区域会聚合数量并展示名单。

资产定位/能效（同一智能体，mock 对齐设备追踪接口）：输液泵12号在哪、哪些设备离线/低电/越界、使用率偏高、妇产科一体机耗电。

## 启动

```bash
cd emergency-rfid-agent-demo
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

需要 `DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY`（当前环境若已有可直接用）。

```bash
# 轻量网页  http://127.0.0.1:7861  （流式输出，公网更顺）
python app.py

# 旧版 Gradio
python app.py --gradio

# 命令行
python app.py --cli

# 问一句
python app.py --once "张三现在在哪个区域，绿通走了多久？"

# Skill 测试（工具单测，不调大模型）
python app.py --test-skills

# 含对话端到端
python app.py --test-skills --e2e
python app.py --test-skills --skill analyze_patient_journey
```

网页里有两个页签：**对话**、**Skill 测试**。对话中还可以直接请求柱状图、饼图和折线图。

## 可以问

- 张三现在在哪个区域，绿通走了多久？
- 门诊号 MZ20260608001 的完整流转轨迹
- 今天谁在抢救室待太久了？
- 各区域平均停留多久，瓶颈在哪？
- 今天各绿通患者数量生成柱状图
- 当前设备在线、离线、低电量做一个饼图
- 在地图上显示张三现在的位置
- 用平面图显示输液泵12号的位置

## 接真实接口

```bash
export RFID_API_BASE=http://ip:port
export RFID_API_TOKEN=your-token
export RFID_BUILD_ID=1
```

真实接口要求 `hospitalNo` 或 `epc` 至少一个；姓名检索是 Demo 扩展。
