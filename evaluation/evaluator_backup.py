import os, sys, json, time, re
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.api_client import VLMAPIClient
import jieba

PUNCT_RE = re.compile(r'[。、，！？；：""''（）【】《》\s\n\r\t.,!?;:\"\'()\[\]{}<>]')
NUM_RE = re.compile(r'\d+\.?\d*%?')
STOP_WORDS = set("的了是在有和等也被都要会能对为这个中与从到把将就也不而但如果因为所以虽然可以已经正在被让给比以及或即")


def extract_content_words(text):
    """用 jieba 分词提取内容词（名词、动词、数字等），过滤停用词"""
    clean = PUNCT_RE.sub('', text)
    words = jieba.lcut(clean)
    content = []
    for w in words:
        w = w.strip()
        if not w or len(w) < 2:
            continue
        if w in STOP_WORDS:
            continue
        content.append(w)
    # 额外提取数字
    nums = NUM_RE.findall(text)
    for n in nums:
        if n not in content:
            content.append(n)
    return content


def compute_match(expected, predicted):
    """基于分词的语义匹配"""
    predicted_lower = predicted.lower()

    # 提取期望答案的内容词
    expected_words = extract_content_words(expected)
    if not expected_words:
        return False

    # 统计匹配数：期望词出现在预测中（包含匹配）
    hit = 0
    for ew in expected_words:
        if ew in predicted_lower:
            hit += 1
        else:
            # 尝试反向：预测中是否包含期望词的子串（如"猫"在"小猫"中）
            for pw in jieba.lcut(PUNCT_RE.sub('', predicted)):
                if ew in pw or pw in ew:
                    hit += 1
                    break

    # 短答案（<=3个词）：至少匹配1个词即OK
    # 长答案（>3个词）：匹配率>=40%即OK
    if len(expected_words) <= 3:
        return hit >= 1
    return hit / len(expected_words) >= 0.4


class Evaluator:
    def __init__(self, dataset_path="data/evaluation_dataset.json", image_base_dir="data/test_images"):
        self.dataset_path = dataset_path
        self.image_base_dir = image_base_dir
        self.api_client = VLMAPIClient()
        self.dataset = []
        self.results = []

    def load_dataset(self):
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            self.dataset = json.load(f)
        print(f"Loaded {len(self.dataset)} items")

    def get_image_path(self, image_filename):
        if "natural_scene" in image_filename:
            return os.path.join(self.image_base_dir, "natural_scene", image_filename)
        return os.path.join(self.image_base_dir, "document", image_filename)

    def evaluate_item(self, item):
        image_path = self.get_image_path(item["image"])
        question = item["question"]
        expected = item["answer"]
        if not os.path.exists(image_path):
            return {"id": item["id"], "predicted": "[IMAGE NOT FOUND]", "response_time": 0, "match": False, "category": item["category"], "sub_category": item["sub_category"], "expected": expected, "question": question, "image": item["image"]}
        start_time = time.time()
        try:
            predicted = self.api_client.call_api(image_path=image_path, question=question, history=None, max_retries=2)
        except Exception as e:
            predicted = f"[ERROR: {e}]"
        response_time = time.time() - start_time
        match = compute_match(expected, predicted)
        return {"id": item["id"], "image": item["image"], "question": question, "expected": expected, "predicted": predicted, "response_time": round(response_time, 2), "category": item["category"], "sub_category": item["sub_category"], "match": match}

    def run_evaluation(self, max_items=None):
        self.load_dataset()
        items = self.dataset[:max_items] if max_items else self.dataset
        print(f"Evaluating {len(items)} items...")
        self.results = []
        for i, item in enumerate(items):
            r = self.evaluate_item(item)
            self.results.append(r)
            s = "OK" if r["match"] else "MISS"
            print(f"[{i+1}/{len(items)}] ID={item['id']} {s} ({r['response_time']}s)")
            time.sleep(0.5)
        print(f"Done. {len(self.results)} items.")

    def compute_metrics(self):
        if not self.results:
            return {}
        total = len(self.results)
        matched = sum(1 for r in self.results if r["match"])
        errors = sum(1 for r in self.results if "[ERROR" in r["predicted"] or "[IMAGE NOT FOUND" in r["predicted"])
        avg_time = sum(r["response_time"] for r in self.results) / total
        cat = {}
        for r in self.results:
            c = r["category"]
            if c not in cat:
                cat[c] = {"total": 0, "match": 0, "time": 0}
            cat[c]["total"] += 1
            if r["match"]:
                cat[c]["match"] += 1
            cat[c]["time"] += r["response_time"]
        for c in cat:
            cat[c]["accuracy"] = round(cat[c]["match"] / cat[c]["total"] * 100, 1)
            cat[c]["avg_time"] = round(cat[c]["time"] / cat[c]["total"], 2)
            del cat[c]["time"]
        sub = {}
        for r in self.results:
            sc = r["sub_category"]
            if sc not in sub:
                sub[sc] = {"total": 0, "match": 0}
            sub[sc]["total"] += 1
            if r["match"]:
                sub[sc]["match"] += 1
        for sc in sub:
            sub[sc]["accuracy"] = round(sub[sc]["match"] / sub[sc]["total"] * 100, 1)
        return {"total": total, "matched": matched, "errors": errors, "accuracy": round(matched/total*100, 1), "avg_response_time": round(avg_time, 2), "category_stats": cat, "sub_category_stats": sub}

    def generate_report(self, output_path="evaluation/evaluation_report.md"):
        m = self.compute_metrics()
        if not m:
            print("No results")
            return
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = []
        lines.append("# 评测报告")
        lines.append("")
        lines.append(f"**生成时间**: {now}")
        lines.append("")
        lines.append("## 总体指标")
        lines.append("")
        lines.append("| 指标 | 值 |")
        lines.append("|------|----|")
        lines.append(f"| 总数据量 | {m['total']} |")
        lines.append(f"| 匹配数 | {m['matched']} |")
        lines.append(f"| 错误数 | {m['errors']} |")
        lines.append(f"| **准确率** | **{m['accuracy']}%** |")
        lines.append(f"| 平均响应时间 | {m['avg_response_time']}s |")
        lines.append("")
        lines.append("## 按类别统计")
        lines.append("")
        lines.append("| 类别 | 数据量 | 准确率 | 平均响应时间 |")
        lines.append("|------|--------|--------|-------------|")
        for c, s in m["category_stats"].items():
            cn = "自然场景" if c == "natural_scene" else "文档图像"
            lines.append(f"| {cn} | {s['total']} | {s['accuracy']}% | {s['avg_time']}s |")
        lines.append("")
        lines.append("## 按子类别统计")
        lines.append("")
        lines.append("| 子类别 | 数据量 | 准确率 |")
        lines.append("|--------|--------|--------|")
        for sc, s in m["sub_category_stats"].items():
            lines.append(f"| {sc} | {s['total']} | {s['accuracy']}% |")
        lines.append("")
        lines.append("## 样例结果（前5条）")
        lines.append("")
        for r in self.results[:5]:
            tag = "OK" if r["match"] else "MISS"
            lines.append(f"- **[{tag}]** Q: {r['question']}")
            lines.append(f"  - 期望: {r['expected']}")
            lines.append(f"  - 预测: {r['predicted'][:100]}")
            lines.append("")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"Report: {output_path}")
        jp = output_path.replace(".md", ".json")
        with open(jp, "w", encoding="utf-8") as f:
            json.dump({"metrics": m, "results": self.results}, f, ensure_ascii=False, indent=2)
        print(f"JSON: {jp}")


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--max-items", type=int, default=None)
    p.add_argument("--dataset", default="data/evaluation_dataset.json")
    p.add_argument("--output", default="evaluation/evaluation_report.md")
    a = p.parse_args()
    e = Evaluator(dataset_path=a.dataset)
    e.run_evaluation(max_items=a.max_items)
    e.generate_report(output_path=a.output)
    m = e.compute_metrics()
    print(f"\nAccuracy: {m['accuracy']}%  AvgTime: {m['avg_response_time']}s")


if __name__ == "__main__":
    main()
