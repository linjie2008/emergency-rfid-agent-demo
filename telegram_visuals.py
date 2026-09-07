"""Render agent visualization payloads to Telegram-friendly PNG files."""

from __future__ import annotations

import math
import json
import secrets
import subprocess
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont


WIDTH, HEIGHT = 1200, 720
BACKGROUND = "#08131d"
PANEL = "#102331"
GRID = "#274252"
TEXT = "#eef8fb"
MUTED = "#90aebb"
COLORS = ("#42e4c1", "#45a9ff", "#ffc75d", "#ff667f", "#a98cff", "#64d889")
OUTPUT_DIR = Path(__file__).resolve().parent / "runtime" / "telegram_visuals"
CHROME_CANDIDATES = (
    Path("/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"),
    Path("/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
)
FONT_REGULAR = Path("/mnt/c/Windows/Fonts/msyh.ttc")
FONT_BOLD = Path("/mnt/c/Windows/Fonts/msyhbd.ttc")


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = FONT_BOLD if bold else FONT_REGULAR
    try:
        return ImageFont.truetype(str(path), size=size)
    except OSError:
        return ImageFont.load_default()


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _short(value: Any, limit: int = 18) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _base(title: str, subtitle: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((28, 24, WIDTH - 28, HEIGHT - 24), radius=24, fill=PANEL, outline="#315267", width=2)
    draw.text((62, 48), _short(title, 34), font=_font(34, True), fill=TEXT)
    draw.text((64, 94), subtitle, font=_font(17), fill=MUTED)
    return image, draw


def _save(image: Image.Image, prefix: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{prefix}_{time.time_ns()}.png"
    image.save(path, "PNG", optimize=True)
    return path


def _footer(draw: ImageDraw.ImageDraw, text: str = "当前智能体隔离数据接口 · 电报可视化") -> None:
    draw.text((62, 674), text, font=_font(15), fill="#6f909e")


def render_chart_png(spec: dict[str, Any]) -> Path:
    chart_type = str(spec.get("type") or "bar")
    unit = str(spec.get("unit") or "")
    image, draw = _base(str(spec.get("title") or "业务数据图表"), f"{chart_type.upper()} · 数据值来自智能体工具")
    box = (72, 148, 1128, 630)
    draw.rounded_rectangle(box, radius=18, fill="#0b1b27", outline=GRID, width=2)

    if chart_type == "pie":
        rows = list(spec.get("data") or [])[:10]
        values = [max(0, _number(item.get("value"))) for item in rows]
        total = sum(values) or 1
        bounds = (142, 184, 532, 574)
        start = -90.0
        for index, (item, value) in enumerate(zip(rows, values)):
            end = start + value / total * 360
            draw.pieslice(bounds, start=start, end=end, fill=COLORS[index % len(COLORS)], outline="#08131d", width=3)
            start = end
        draw.ellipse((242, 284, 432, 474), fill="#0b1b27", outline="#29495b", width=2)
        draw.text((337, 336), f"{total:g}{unit}", anchor="mm", font=_font(30, True), fill=TEXT)
        draw.text((337, 376), "合计", anchor="mm", font=_font(17), fill=MUTED)
        for index, (item, value) in enumerate(zip(rows, values)):
            y = 192 + index * 42
            draw.rounded_rectangle((610, y, 626, y + 16), radius=4, fill=COLORS[index % len(COLORS)])
            label = f"{_short(item.get('name'), 16)}  {value:g}{unit}  {value / total * 100:.1f}%"
            draw.text((642, y - 5), label, font=_font(19, index < 3), fill=TEXT if index < 3 else MUTED)
    elif chart_type == "gauge":
        item = (spec.get("data") or [{}])[0]
        value, maximum = _number(item.get("value")), _number(item.get("max")) or 100
        ratio = min(1, max(0, value / maximum))
        bounds = (300, 194, 900, 794)
        draw.arc(bounds, start=200, end=340, fill="#294858", width=48)
        draw.arc(bounds, start=200, end=200 + 140 * ratio, fill=COLORS[0] if ratio >= .8 else COLORS[2], width=48)
        draw.text((600, 430), f"{value:g}{unit}", anchor="mm", font=_font(64, True), fill=TEXT)
        draw.text((600, 490), _short(item.get("name") or "当前指标", 28), anchor="mm", font=_font(25), fill=MUTED)
    elif chart_type == "radar":
        categories = list(spec.get("categories") or [])[:10]
        series = list(spec.get("series") or [])[:4]
        cx, cy, radius = 600, 390, 205
        count = max(3, len(categories))
        maximum = max([_number(v) for row in series for v in row.get("data", [])] or [100]) or 100
        for level in range(1, 6):
            points = [(cx + radius * level / 5 * math.cos(-math.pi / 2 + i * 2 * math.pi / count), cy + radius * level / 5 * math.sin(-math.pi / 2 + i * 2 * math.pi / count)) for i in range(count)]
            draw.polygon(points, outline=GRID)
        for index, category in enumerate(categories):
            angle = -math.pi / 2 + index * 2 * math.pi / count
            end = (cx + radius * math.cos(angle), cy + radius * math.sin(angle))
            draw.line((cx, cy, *end), fill=GRID, width=1)
            draw.text((cx + (radius + 35) * math.cos(angle), cy + (radius + 35) * math.sin(angle)), _short(category, 8), anchor="mm", font=_font(16), fill=MUTED)
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0)); od = ImageDraw.Draw(overlay)
        for index, row in enumerate(series):
            values = list(row.get("data") or [])
            points = [(cx + radius * min(1, _number(values[i]) / maximum) * math.cos(-math.pi / 2 + i * 2 * math.pi / count), cy + radius * min(1, _number(values[i]) / maximum) * math.sin(-math.pi / 2 + i * 2 * math.pi / count)) for i in range(min(count, len(values)))]
            if len(points) >= 3:
                color = COLORS[index % len(COLORS)]
                od.polygon(points, fill=color + "32", outline=color)
        image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(image)
    else:
        categories = list(spec.get("categories") or [])[:16]
        series = list(spec.get("series") or [])[:5]
        left, top, right, bottom = 130, 190, 1080, 570
        all_values = [_number(value) for row in series for value in row.get("data", [])]
        maximum = max(all_values or [1]) or 1
        for level in range(6):
            y = bottom - (bottom - top) * level / 5
            draw.line((left, y, right, y), fill=GRID, width=1)
            draw.text((left - 18, y), f"{maximum * level / 5:g}", anchor="rm", font=_font(14), fill=MUTED)
        count = max(1, len(categories))
        if chart_type == "bar":
            group = (right - left) / count
            bar_width = max(6, min(38, group * .7 / max(1, len(series))))
            for series_index, row in enumerate(series):
                for index, value in enumerate(row.get("data", [])[:count]):
                    height = _number(value) / maximum * (bottom - top)
                    x = left + index * group + group * .15 + series_index * bar_width
                    draw.rounded_rectangle((x + 5, bottom - height + 6, x + bar_width + 5, bottom + 6), radius=4, fill="#041019")
                    draw.rounded_rectangle((x, bottom - height, x + bar_width, bottom), radius=4, fill=COLORS[series_index % len(COLORS)])
        else:
            for series_index, row in enumerate(series):
                values = list(row.get("data") or [])[:count]
                points = [(left + (right - left) * index / max(1, count - 1), bottom - _number(value) / maximum * (bottom - top)) for index, value in enumerate(values)]
                if chart_type == "area" and len(points) > 1:
                    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0)); od = ImageDraw.Draw(overlay)
                    od.polygon([*points, (points[-1][0], bottom), (points[0][0], bottom)], fill=COLORS[series_index % len(COLORS)] + "30")
                    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB"); draw = ImageDraw.Draw(image)
                if len(points) > 1:
                    draw.line(points, fill=COLORS[series_index % len(COLORS)], width=5, joint="curve")
                for point in points:
                    draw.ellipse((point[0]-5, point[1]-5, point[0]+5, point[1]+5), fill=COLORS[series_index % len(COLORS)], outline="#ffffff", width=1)
        step = max(1, math.ceil(count / 8))
        for index, category in enumerate(categories):
            if index % step == 0:
                x = left + (right - left) * (index + .5) / count if chart_type == "bar" else left + (right - left) * index / max(1, count - 1)
                draw.text((x, bottom + 18), _short(category, 8), anchor="ma", font=_font(14), fill=MUTED)
        for index, row in enumerate(series):
            x = 160 + index * 190
            draw.rectangle((x, 602, x + 18, 614), fill=COLORS[index % len(COLORS)])
            draw.text((x + 27, 594), _short(row.get("name"), 12), font=_font(16), fill=TEXT)
    _footer(draw)
    return _save(image, "chart")


def _xy(point: dict[str, Any], plot: tuple[int, int, int, int]) -> tuple[float, float]:
    left, top, right, bottom = plot
    return left + _number(point.get("x")) / 100 * (right - left), top + _number(point.get("y")) / 100 * (bottom - top)


def render_trajectory_png(spec: dict[str, Any]) -> Path:
    summary = spec.get("summary") or {}
    subject = str(spec.get("subject") or "定位对象")
    image, draw = _base(f"{subject} · 轨迹与停留热力图", f"最高停留：{summary.get('hottestArea', '--')}   时段：{summary.get('timeRange', '--')}   采样：{summary.get('samplePoints', 0)} 点")
    plot = (68, 144, 1132, 622)
    draw.rounded_rectangle(plot, radius=18, fill="#071923", outline=GRID, width=2)
    for zone in (spec.get("layout") or {}).get("zones", []):
        left, top = _xy(zone, plot)
        right, bottom = _xy({"x": _number(zone.get("x")) + _number(zone.get("w")), "y": _number(zone.get("y")) + _number(zone.get("h"))}, plot)
        risk = zone.get("kind") == "risk"
        color = "#ff667f" if risk else ("#ffc75d" if zone.get("kind") == "fence" else "#32758b")
        draw.rounded_rectangle((left, top, right, bottom), radius=10, fill="#102a37", outline=color, width=2)
        draw.text((left + 10, top + 8), _short(zone.get("name"), 12), font=_font(15, True), fill=color if risk else MUTED)

    points = list(spec.get("heatmap") or spec.get("points") or [])
    heat = Image.new("RGBA", image.size, (0, 0, 0, 0)); hd = ImageDraw.Draw(heat)
    maximum = max([_number(point.get("weight")) for point in points] or [1]) or 1
    for point in points:
        x, y = _xy(point, plot); ratio = _number(point.get("weight")) / maximum
        radius = 28 + ratio * 42
        color = (255, 75, 100, int(70 + ratio * 95)) if ratio > .66 else ((255, 199, 75, int(55 + ratio * 80)) if ratio > .35 else (45, 220, 195, 60))
        hd.ellipse((x-radius, y-radius, x+radius, y+radius), fill=color)
    heat = heat.filter(ImageFilter.GaussianBlur(24))
    image = Image.alpha_composite(image.convert("RGBA"), heat).convert("RGB"); draw = ImageDraw.Draw(image)

    tracks = list(spec.get("tracks") or [])
    if not tracks:
        tracks = [{"name": subject, "color": COLORS[0], "points": spec.get("points") or [], "keyPoints": spec.get("keyPoints") or []}]
    for index, track in enumerate(tracks):
        color = str(track.get("color") or COLORS[index % len(COLORS)])
        track_points = [_xy(point, plot) for point in (track.get("points") or [])]
        if len(track_points) > 1:
            draw.line(track_points, fill="#031018", width=8, joint="curve")
            draw.line(track_points, fill=color, width=3, joint="curve")
        keys = track.get("keyPoints") or []
        for key_index, point in enumerate(keys):
            x, y = _xy(point, plot)
            draw.ellipse((x-7, y-7, x+7, y+7), fill="#071923", outline=color, width=3)
            if spec.get("mode") != "group" or key_index == len(keys) - 1:
                label = track.get("name") if spec.get("mode") == "group" else point.get("area")
                draw.rounded_rectangle((x-58, y-34, x+58, y-13), radius=5, fill="#06131ccc", outline=color)
                draw.text((x, y-25), _short(label, 10), anchor="mm", font=_font(13, True), fill=TEXT)
    _footer(draw, f"{spec.get('source') or '当前智能体轨迹接口'} · 红色表示停留强度较高")
    return _save(image, "heatmap")


def render_map_png(spec: dict[str, Any]) -> Path:
    image, draw = _base(str(spec.get("title") or "实时位置图"), f"{spec.get('floor') or '当前区域'} · {spec.get('subject') or '定位对象'} · {spec.get('status') or '实时'}")
    plot = (68, 144, 1132, 622)
    draw.rounded_rectangle(plot, radius=18, fill="#071923", outline=GRID, width=2)
    areas = list(spec.get("areas") or [])
    area_centers: dict[str, tuple[float, float]] = {}
    for area in areas:
        if all(key in area for key in ("x", "y", "w", "h")):
            left, top = _xy(area, plot)
            right, bottom = _xy({"x": _number(area["x"]) + _number(area["w"]), "y": _number(area["y"]) + _number(area["h"])}, plot)
        else:
            index = areas.index(area); columns = 4
            width, height = 235, 180
            left = 90 + (index % columns) * 255; top = 170 + (index // columns) * 205
            right, bottom = left + width, top + height
        name = str(area.get("name") or area.get("area") or f"区域{areas.index(area)+1}")
        area_centers[name] = ((left + right) / 2, (top + bottom) / 2)
        draw.rounded_rectangle((left, top, right, bottom), radius=10, fill="#102a37", outline="#32758b", width=2)
        draw.text((left + 10, top + 8), _short(name, 14), font=_font(15, True), fill=MUTED)
    markers = list(spec.get("markers") or [])
    for index, marker in enumerate(markers[:30]):
        center = next((point for name, point in area_centers.items() if name in str(marker.get("position") or "") or str(marker.get("position") or "") in name), None)
        if center is None:
            center = (140 + (index % 8) * 125, 220 + (index // 8) * 95)
        offset = ((index % 3) - 1) * 24
        x, y = center[0] + offset, center[1] + ((index // 3) % 3 - 1) * 22
        alarm = marker.get("alarm") not in (None, "", "无报警") or marker.get("status") in {"离线", "异常"}
        color = COLORS[3] if alarm else COLORS[0]
        draw.ellipse((x-11, y-11, x+11, y+11), fill=color, outline="#ffffff", width=2)
        draw.text((x, y+18), _short(marker.get("name"), 9), anchor="ma", font=_font(13, True), fill=TEXT)
    _footer(draw, f"定位对象 {len(markers)} 个 · 当前智能体实时定位接口")
    return _save(image, "map")


def _render_visual_event_pillow(event: dict[str, Any]) -> Path | None:
    kind = event.get("type")
    if kind == "chart" and event.get("chart"):
        return render_chart_png(event["chart"])
    if kind == "trajectory" and event.get("trajectory"):
        return render_trajectory_png(event["trajectory"])
    if kind == "map" and event.get("map"):
        return render_map_png(event["map"])
    return None


def _windows_path(path: Path) -> str:
    result = subprocess.run(["wslpath", "-w", str(path)], capture_output=True, text=True, timeout=5, check=False)
    return result.stdout.strip()


def _render_with_pc_page(event: dict[str, Any], scene: str) -> Path | None:
    browser = next((path for path in CHROME_CANDIDATES if path.is_file()), None)
    if browser is None:
        return None
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(16)
    task_path = OUTPUT_DIR / f"{token}.json"
    output_path = OUTPUT_DIR / f"web_{token}.png"
    task_path.write_text(json.dumps(event, ensure_ascii=False), encoding="utf-8")
    try:
        windows_output = _windows_path(output_path)
        if not windows_output:
            return None
        url = f"http://127.0.0.1:7861/?scene={scene}&telegram_visual={token}"
        command = [
            str(browser), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--incognito",
            "--force-device-scale-factor=1", "--window-size=1200,720", "--virtual-time-budget=5000",
            f"--screenshot={windows_output}", url,
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=35, check=False)
        if result.returncode == 0 and output_path.is_file() and output_path.stat().st_size > 5000:
            return output_path
        return None
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        try:
            task_path.unlink(missing_ok=True)
        except OSError:
            pass


def render_visual_event(event: dict[str, Any], scene: str = "safety") -> Path | None:
    """优先复用 PC 页面渲染结果；无头浏览器失败时使用 Pillow 保底。"""
    rendered = _render_with_pc_page(event, scene)
    return rendered or _render_visual_event_pillow(event)
