from PIL import Image

import telegram_bot
from platform_features import trajectory_payload
from telegram_visuals import render_chart_png, render_trajectory_png


def test_visual_renderers_create_uniform_telegram_png():
    chart = render_chart_png({
        "type": "pie", "title": "告警分布", "unit": "条",
        "data": [{"name": "高风险", "value": 3}, {"name": "一般", "value": 8}],
    })
    heatmap = render_trajectory_png(trajectory_payload("eldercare", "所有老人"))
    for path in (chart, heatmap):
        assert path.is_file()
        with Image.open(path) as image:
            assert image.size == (1200, 720)


def test_charts_and_heatmaps_are_not_misrouted_to_comfyui():
    for question in ("生成考勤柱状图", "画一个告警饼图", "生成所有老人热力图", "显示人员位置图"):
        assert telegram_bot.is_visualization_request(question)
        assert not (telegram_bot.is_diagram_request(question) and not telegram_bot.is_visualization_request(question))
