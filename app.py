#!/usr/bin/env python3
"""急诊绿通 RFID 对话 Demo。

  python app.py                打开轻量网页（对话 + Skill 测试）
  python app.py --gradio       旧版 Gradio 界面
  python app.py --cli          命令行对话
  python app.py --once "问题"
  python app.py --test-skills            跑工具 Skill 测试
  python app.py --test-skills --e2e      含大模型端到端
"""

from __future__ import annotations

import argparse
import uuid

from agent import ask, build_agent
from skill_test import format_report, results_table, run_skill_tests
from skills import SKILL_CATALOG, parse_skill_choice, skill_choices

EXAMPLES = [
    "张三现在在哪个区域，绿通走了多久？",
    "门诊号 MZ20260608001 的完整流转轨迹",
    "今天谁在抢救室待太久了？",
    "各区域平均停留多久，瓶颈在哪？",
    "李四溶栓前后的节点时间",
]


def run_once(question: str) -> str:
    agent = build_agent()
    return ask(agent, question, thread_id="once")


def run_cli() -> None:
    agent = build_agent()
    thread_id = f"cli-{uuid.uuid4().hex[:8]}"
    print("急诊绿通 RFID 智能体  （输入 q 退出）")
    print("可以问：")
    for q in EXAMPLES:
        print(f"  - {q}")
    print()
    while True:
        try:
            q = input("你：").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not q or q.lower() in {"q", "quit", "exit"}:
            break
        print("助手：", ask(agent, q, thread_id), flush=True)
        print()


def run_skill_cli(include_e2e: bool, skill_id: str | None = None) -> int:
    report = run_skill_tests(skill_id=skill_id, include_e2e=include_e2e)
    print(format_report(report))
    return 0 if report["failed"] == 0 else 1


def run_web() -> None:
    import gradio as gr

    agent = build_agent()
    catalog_md = "\n".join(
        f"- `{s['id']}` **{s['name']}**（{s['kind']}）：{s['description']}"
        for s in SKILL_CATALOG
    )

    def respond(message, history):
        history = history or []
        if not (message or "").strip():
            return history
        sid = f"web-{abs(hash(str(history[:1]))) % 10_000_000}"
        answer = ask(agent, message, thread_id=sid)
        return history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": answer},
        ]

    def run_tests(choice: str, include_e2e: bool):
        skill_id = parse_skill_choice(choice)
        if skill_id in {"", "全部 Skill"}:
            skill_id = None
        report = run_skill_tests(
            skill_id=skill_id,
            include_e2e=include_e2e,
            agent=agent if include_e2e else None,
        )
        summary = (
            f"**{report['passed']}/{report['total']} 通过**"
            + (f"，失败 {report['failed']}" if report["failed"] else "")
        )
        detail = format_report(report)
        return summary, results_table(report), detail

    with gr.Blocks(title="急诊绿通 RFID Demo") as demo:
        gr.Markdown(
            "# 急诊绿通 · RFID 智能查询 Demo\n"
            "LangGraph 智能体。数字全部由 Skill 从进出记录计算，不让模型估。"
        )
        with gr.Tabs():
            with gr.Tab("对话"):
                chatbot = gr.Chatbot(label="对话", height=460)
                question = gr.Textbox(label="提问", placeholder="例如：张三现在在哪？")
                send = gr.Button("发送", variant="primary")
                gr.Examples(EXAMPLES, inputs=question)
                send.click(respond, [question, chatbot], chatbot).then(
                    lambda: "", None, question
                )
                question.submit(respond, [question, chatbot], chatbot).then(
                    lambda: "", None, question
                )

            with gr.Tab("Skill 测试"):
                gr.Markdown(
                    "先测工具 Skill（不调大模型），需要时再勾选端到端，检查对话有没有调对 Skill、回答有没有关键字段。\n\n"
                    + catalog_md
                )
                with gr.Row():
                    skill_dd = gr.Dropdown(
                        choices=["全部 Skill", *skill_choices()],
                        value="全部 Skill",
                        label="要测的 Skill",
                    )
                    e2e = gr.Checkbox(label="包含大模型端到端（较慢）", value=False)
                run_btn = gr.Button("运行测试", variant="primary")
                summary = gr.Markdown()
                table = gr.Dataframe(
                    headers=["结果", "Skill", "用例", "耗时ms", "调用", "说明"],
                    wrap=True,
                    interactive=False,
                )
                detail = gr.Textbox(label="明细", lines=16)
                run_btn.click(run_tests, [skill_dd, e2e], [summary, table, detail])

    demo.launch(server_name="0.0.0.0", server_port=7861, inbrowser=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="急诊绿通 RFID Agent Demo")
    parser.add_argument("--cli", action="store_true", help="命令行模式")
    parser.add_argument("--once", metavar="问题", help="问一句后退出")
    parser.add_argument("--test-skills", action="store_true", help="运行 Skill 测试")
    parser.add_argument("--e2e", action="store_true", help="Skill 测试含大模型端到端")
    parser.add_argument("--skill", metavar="ID", help="只测某一个 Skill，如 analyze_patient_journey")
    parser.add_argument("--gradio", action="store_true", help="使用 Gradio 界面（更重，公网更慢）")
    args = parser.parse_args()
    if args.test_skills:
        raise SystemExit(run_skill_cli(include_e2e=args.e2e, skill_id=args.skill))
    if args.once:
        print(run_once(args.once))
    elif args.cli:
        run_cli()
    elif args.gradio:
        run_web()
    else:
        from server import serve

        serve()


if __name__ == "__main__":
    main()
