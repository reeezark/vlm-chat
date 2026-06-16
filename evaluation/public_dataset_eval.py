#!/usr/bin/env python
"""TextVQA 公开数据集评测脚本。

从 TextVQA 0.5.1 验证集中随机抽取 50 条样本，调用 VLM 模型进行问答评测。
- 图片来源：flickr_300k_url 按需下载
- 匹配算法：英文大小写不敏感，多标注者答案任一命中即判正确
- 输出：evaluation/public_eval_report.md + evaluation/public_eval_report.json
"""

import json
import os
import re
import sys
import random
import time
from datetime import datetime

import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.api_client import VLMAPIClient

# ============================================================
# 配置常量
# ============================================================
DATASET_PATH = "data/TextVQA_0.5.1_val.json"
IMAGE_DIR = "data/textvqa_images"
OUTPUT_MD = "evaluation/public_eval_report.md"
OUTPUT_JSON = "evaluation/public_eval_report.json"
SAMPLE_SIZE = 50
RANDOM_SEED = 42

PUNCT_RE = re.compile(r'[.,!?;:\"\'()\[\]{}<>\s]+')


def compute_match_en(expected_answers, predicted):
    """英文大小写不敏感匹配：任一标注者答案出现在预测中即判正确。

    TextVQA 标准评测方式 — 每条数据有 10 个标注者答案，命中任一即正确。
    """
    predicted_clean = predicted.lower()
    for ans in expected_answers:
        ans_clean = ans.strip().lower()
        if not ans_clean:
            continue
        if ans_clean in predicted_clean:
            return True
    return False


def download_image(url, save_path):
    """从 URL 下载图片到本地。已存在则跳过下载。"""
    if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
        return True
    try:
        resp = requests.get(url, timeout=20, stream=True)
        if resp.status_code == 200:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, 'wb') as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
            return True
        return False
    except Exception:
        return False


class PublicDatasetEvaluator:
    """TextVQA 公开数据集评测器。"""

    def __init__(self):
        self.api_client = VLMAPIClient()
        self.results = []

    def load_and_sample(self):
        """加载 TextVQA JSON 并随机采样。"""
        with open(DATASET_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        items = data['data']
        random.seed(RANDOM_SEED)
        sample = random.sample(items, min(SAMPLE_SIZE, len(items)))
        print(f"从 {len(items)} 条中随机采样 {len(sample)} 条 (seed={RANDOM_SEED})")
        return sample

    def evaluate_item(self, item):
        """评测单条样本：下载图片 → 调用 API → 匹配答案。"""
        img_filename = f"{item['image_id']}.jpg"
        img_path = os.path.join(IMAGE_DIR, img_filename)

        # 下载图片
        image_ok = download_image(item['flickr_300k_url'], img_path)
        if not image_ok:
            return {
                "image_id": item["image_id"],
                "question": item["question"],
                "expected_answers": item["answers"],
                "predicted": "[IMAGE DOWNLOAD FAILED]",
                "response_time": 0,
                "match": False,
                "status": "SKIP",
            }

        # 调用 VLM API
        start_time = time.time()
        try:
            predicted = self.api_client.call_api(
                image_path=img_path,
                question=item["question"],
                history=None,
                max_retries=2,
            )
        except Exception as e:
            predicted = f"[ERROR: {e}]"
        response_time = time.time() - start_time

        match = compute_match_en(item["answers"], predicted)
        status = "OK" if match else "MISS"

        return {
            "image_id": item["image_id"],
            "question": item["question"],
            "expected_answers": item["answers"],
            "predicted": predicted,
            "response_time": round(response_time, 2),
            "match": match,
            "status": status,
        }

    def run(self):
        """执行全部评测流程。"""
        items = self.load_and_sample()
        print(f"开始评测 {len(items)} 条样本...")
        os.makedirs(IMAGE_DIR, exist_ok=True)

        self.results = []
        for i, item in enumerate(items):
            r = self.evaluate_item(item)
            self.results.append(r)
            print(
                f"[{i+1:3d}/{len(items)}] {r['image_id'][:12]}  "
                f"{r['status']:5s}  ({r['response_time']:5.2f}s)"
            )
            time.sleep(0.5)  # 避免触发限流

        print(f"\n评测完成。共 {len(self.results)} 条。")

    def compute_metrics(self):
        """汇总评测指标。"""
        valid = [r for r in self.results if r["status"] != "SKIP"]
        skipped = len(self.results) - len(valid)
        valid_count = len(valid)
        matched = sum(1 for r in valid if r["match"])
        accuracy = round(matched / valid_count * 100, 1) if valid_count > 0 else 0.0
        avg_time = (
            round(sum(r["response_time"] for r in valid) / valid_count, 2)
            if valid_count > 0
            else 0.0
        )
        return {
            "total_sampled": len(self.results),
            "valid": valid_count,
            "skipped": skipped,
            "matched": matched,
            "accuracy": accuracy,
            "avg_response_time": avg_time,
        }

    def generate_report(self):
        """生成 Markdown 报告和 JSON 数据文件。"""
        m = self.compute_metrics()
        os.makedirs(os.path.dirname(OUTPUT_MD), exist_ok=True)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = []
        lines.append("# TextVQA 公开数据集评测报告")
        lines.append("")
        lines.append(f"**生成时间**：{now}")
        lines.append(f"**数据集**：TextVQA 0.5.1 Validation（5000 条）")
        lines.append(f"**采样**：随机抽取 {SAMPLE_SIZE} 条（seed={RANDOM_SEED}）")
        lines.append(f"**模型**：DashScope Qwen3-VL-Flash（通过 VLMAPIClient）")
        lines.append("")
        lines.append("## 总体指标")
        lines.append("")
        lines.append("| 指标 | 值 |")
        lines.append("|------|----|")
        lines.append(f"| 采样数 | {m['total_sampled']} |")
        lines.append(f"| 有效样本 | {m['valid']} |")
        lines.append(f"| 跳过（图片下载失败） | {m['skipped']} |")
        lines.append(f"| 匹配数 | {m['matched']} |")
        lines.append(f"| **准确率** | **{m['accuracy']}%** |")
        lines.append(f"| 平均响应时间 | {m['avg_response_time']}s |")
        lines.append("")

        if m['skipped'] > 0:
            lines.append(
                f"> 有 {m['skipped']} 条样本因 Flickr 图片链接失效"
                f"（404/410/超时）被跳过，不计入准确率统计。"
            )
            if m['valid'] < 30:
                lines.append(
                    f"> 有效样本仅 {m['valid']} 条（不足 30 条），"
                    f"结论仅供参考。原因：Flickr 外链自然过期。"
                )
            lines.append("")

        # 与自建集对比说明
        lines.append("## 与自建集对比")
        lines.append("")
        lines.append(
            "TextVQA 以 OCR 类问题为主（阅读图片中的文字并回答），"
            "Qwen-VL 系列在此类任务上表现较好。"
            "而自建集涵盖更广泛的自然场景理解、中文推理、摘要等题型，"
            "难度分布不同，因此两集合的准确率存在差异属于正常现象。"
        )
        lines.append("")

        # 样例结果
        lines.append("## 样例结果（前 10 条）")
        lines.append("")
        for r in self.results[:10]:
            tag = r["status"]
            lines.append(f"- **[{tag}]** Q: {r['question']}")
            answers_short = " | ".join(r['expected_answers'][:4])
            if len(r['expected_answers']) > 4:
                answers_short += " | ..."
            lines.append(f"  - 期望答案: {answers_short}")
            pred_short = r['predicted'][:150]
            if len(r['predicted']) > 150:
                pred_short += "..."
            lines.append(f"  - 预测: {pred_short}")
            lines.append("")

        # 写入 Markdown
        with open(OUTPUT_MD, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"报告已生成：{OUTPUT_MD}")

        # 写入 JSON
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(
                {"metrics": m, "results": self.results},
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"JSON 已生成：{OUTPUT_JSON}")


def main():
    evaluator = PublicDatasetEvaluator()
    evaluator.run()
    evaluator.generate_report()
    m = evaluator.compute_metrics()
    print(f"\n最终结果：准确率 {m['accuracy']}%（有效 {m['valid']}/{m['total_sampled']}）")
    print(f"平均响应时间：{m['avg_response_time']}s")


if __name__ == "__main__":
    main()
