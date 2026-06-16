#!/usr/bin/env python
"""生成可视化图表。

数据来源：
  - evaluation/evaluation_report.json   （自建集80条）
  - evaluation/public_eval_report.json  （TextVQA公开集50条）

输出（evaluation/figures/）：
  - category_accuracy.png     图1：类别准确率对比柱状图
  - subcategory_accuracy.png  图2：子类别准确率水平条形图
  - response_time.png         图3：响应时间箱线图
"""

import json
import os
import sys

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

# ============================================================
# 字体与样式配置
# ============================================================
matplotlib.rcParams["font.sans-serif"] = [
    "SimHei",
    "Microsoft YaHei",
    "Droid Sans Fallback",
    "DejaVu Sans",
]
matplotlib.rcParams["axes.unicode_minus"] = False

# 配色
BAR_COLORS = ["#4C72B0", "#55A868", "#C44E52"]
SUB_COLORS = ["#4C72B0", "#55A868", "#C44E52", "#8172B2", "#CCB974"]

OUTPUT_DIR = "evaluation/figures"
SELF_JSON = "evaluation/evaluation_report.json"
PUBLIC_JSON = "evaluation/public_eval_report.json"
DPI = 150


def load_data():
    """加载自建集和公开集评测数据。"""
    with open(SELF_JSON, "r", encoding="utf-8") as f:
        self_data = json.load(f)
    with open(PUBLIC_JSON, "r", encoding="utf-8") as f:
        public_data = json.load(f)
    return self_data, public_data


def figure1_category_accuracy(self_data, public_data):
    """图1：类别准确率对比柱状图。

    横轴：自然场景 / 文档图像 / TextVQA（公开集）
    纵轴：准确率(%)，ylim=(0, 100)
    """
    cat = self_data["metrics"]["category_stats"]
    natural_acc = cat["natural_scene"]["accuracy"]
    document_acc = cat["document"]["accuracy"]
    public_acc = public_data["metrics"]["accuracy"]

    categories = ["自然场景\n(自建集)", "文档图像\n(自建集)", "TextVQA\n(公开集)"]
    values = [natural_acc, document_acc, public_acc]

    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(categories, values, color=BAR_COLORS, width=0.5, edgecolor="white")

    # 数值标注
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1.5,
            f"{val}%",
            ha="center",
            va="bottom",
            fontsize=13,
            fontweight="bold",
        )

    ax.set_ylabel("准确率 (%)", fontsize=12)
    ax.set_title("图1：类别准确率对比", fontsize=14, fontweight="bold")
    ax.set_ylim(0, 105)
    ax.grid(axis="y", alpha=0.3, linestyle="--")

    # 在自然场景/文档图像柱体上标注数据量
    ax.annotate(
        f"n={cat['natural_scene']['total']}",
        xy=(0, natural_acc / 2),
        ha="center",
        fontsize=10,
        color="white",
        fontweight="bold",
    )
    ax.annotate(
        f"n={cat['document']['total']}",
        xy=(1, document_acc / 2),
        ha="center",
        fontsize=10,
        color="white",
        fontweight="bold",
    )
    ax.annotate(
        f"n={public_data['metrics']['valid']}"
        f"（跳过{public_data['metrics']['skipped']}）",
        xy=(2, public_acc / 2),
        ha="center",
        fontsize=10,
        color="white",
        fontweight="bold",
    )

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "category_accuracy.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {path}")


def figure2_subcategory_accuracy(self_data):
    """图2：子类别准确率水平条形图。

    五个子类别：recognition / attribute / reasoning / ocr / summary
    """
    sub = self_data["metrics"]["sub_category_stats"]

    # 中文标签映射
    label_map = {
        "recognition": "物体识别\n(recognition)",
        "attribute": "属性描述\n(attribute)",
        "reasoning": "推理判断\n(reasoning)",
        "ocr": "文字识别\n(ocr)",
        "summary": "摘要总结\n(summary)",
    }

    labels = []
    values = []
    totals = []
    for key in ["recognition", "attribute", "reasoning", "ocr", "summary"]:
        s = sub[key]
        labels.append(label_map.get(key, key))
        values.append(s["accuracy"])
        totals.append(s["total"])

    # 水平条形图：按准确率倒序排列
    sorted_idx = np.argsort(values)
    labels = [labels[i] for i in sorted_idx]
    values = [values[i] for i in sorted_idx]
    totals = [totals[i] for i in sorted_idx]
    colors = [SUB_COLORS[i] for i in sorted_idx]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.barh(labels, values, color=colors, height=0.55, edgecolor="white")

    # 数值标注
    for bar, val, total in zip(bars, values, totals):
        ax.text(
            bar.get_width() + 1.5,
            bar.get_y() + bar.get_height() / 2,
            f"{val}%  (n={total})",
            va="center",
            fontsize=11,
        )

    ax.set_xlabel("准确率 (%)", fontsize=12)
    ax.set_title("图2：子类别准确率（自建集）", fontsize=14, fontweight="bold")
    ax.set_xlim(0, 105)
    ax.grid(axis="x", alpha=0.3, linestyle="--")

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "subcategory_accuracy.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {path}")


def figure3_response_time(self_data):
    """图3：响应时间箱线图。

    分 natural_scene 和 document 两组，展示分布差异。
    """
    results = self_data["results"]

    natural_times = [
        r["response_time"] for r in results if r["category"] == "natural_scene"
    ]
    document_times = [
        r["response_time"] for r in results if r["category"] == "document"
    ]

    fig, ax = plt.subplots(figsize=(7, 5))

    bp = ax.boxplot(
        [natural_times, document_times],
        tick_labels=["自然场景\n(natural_scene)", "文档图像\n(document)"],
        patch_artist=True,
        widths=0.45,
        showmeans=True,
        meanprops=dict(marker="D", markerfacecolor="white", markeredgecolor="#333333", markersize=7),
        medianprops=dict(color="#333333", linewidth=2),
    )

    # 配色
    for patch, color in zip(bp["boxes"], BAR_COLORS[:2]):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)

    # 叠加散点（抖动）
    for i, times in enumerate([natural_times, document_times]):
        jitter = np.random.default_rng(42).uniform(-0.12, 0.12, len(times))
        x = np.full(len(times), i + 1) + jitter
        ax.scatter(x, times, alpha=0.35, s=20, color="#333333", edgecolors="none", zorder=3)

    # 标注均值
    for i, times in enumerate([natural_times, document_times]):
        mean_val = np.mean(times)
        ax.annotate(
            f"均值 {mean_val:.1f}s",
            xy=(i + 1, mean_val),
            xytext=(i + 1 + 0.25, mean_val + 0.3),
            fontsize=10,
            color="#C44E52",
            fontweight="bold",
        )

    ax.set_ylabel("响应时间 (秒)", fontsize=12)
    ax.set_title("图3：响应时间分布（自建集）", fontsize=14, fontweight="bold")
    ax.grid(axis="y", alpha=0.3, linestyle="--")

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "response_time.png")
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {path}")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    self_data, public_data = load_data()

    print("生成可视化图表...")
    figure1_category_accuracy(self_data, public_data)
    figure2_subcategory_accuracy(self_data)
    figure3_response_time(self_data)

    print(f"\n全部完成。图表输出目录：{OUTPUT_DIR}/")
    for f in os.listdir(OUTPUT_DIR):
        fpath = os.path.join(OUTPUT_DIR, f)
        size_kb = os.path.getsize(fpath) / 1024
        print(f"  {f}  ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
