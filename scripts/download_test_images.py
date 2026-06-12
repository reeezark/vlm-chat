"""
下载真实测试图片并生成逼真文档图片
替换 PIL 生成的占位色块
"""
import os
import sys
import time
import requests
from PIL import Image, ImageDraw, ImageFont

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_DIR = "data/test_images"
NATURAL_DIR = os.path.join(BASE_DIR, "natural_scene")
DOCUMENT_DIR = os.path.join(BASE_DIR, "document")

# Pixabay 免费图片直链（按 dataset 中的问题内容选取）
NATURAL_IMAGES = [
    ("https://cdn.pixabay.com/photo/2024/02/28/07/42/european-shorthair-8601492_640.jpg", "natural_scene_001.jpg"),
    ("https://cdn.pixabay.com/photo/2015/12/01/20/28/road-1072821_640.jpg", "natural_scene_002.jpg"),
    ("https://cdn.pixabay.com/photo/2015/04/19/08/32/marguerite-729510_640.jpg", "natural_scene_005.jpg"),
    ("https://cdn.pixabay.com/photo/2016/11/22/22/18/bicycle-1850263_640.jpg", "natural_scene_007.jpg"),
    ("https://cdn.pixabay.com/photo/2017/07/18/15/16/golden-retriever-2516557_640.jpg", "natural_scene_010.jpg"),
    ("https://cdn.pixabay.com/photo/2016/08/28/23/14/sunflower-1627193_640.jpg", "natural_scene_012.jpg"),
    ("https://cdn.pixabay.com/photo/2010/12/13/10/05/berries-2210_640.jpg", "natural_scene_014.jpg"),
    ("https://cdn.pixabay.com/photo/2019/11/08/11/36/cat-4611189_640.jpg", "natural_scene_016.jpg"),
    ("https://cdn.pixabay.com/photo/2017/02/07/16/47/kingfisher-2046453_640.jpg", "natural_scene_020.jpg"),
    ("https://cdn.pixabay.com/photo/2019/08/19/07/45/corgi-4415649_640.jpg", "natural_scene_030.jpg"),
]


def download_image(url, save_path, max_retries=3):
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            if resp.status_code == 200 and len(resp.content) > 1000:
                with open(save_path, "wb") as f:
                    f.write(resp.content)
                return True
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(1)
    return False


def download_natural_scene_images():
    os.makedirs(NATURAL_DIR, exist_ok=True)
    print(f"Downloading {len(NATURAL_IMAGES)} natural scene images...")
    success = 0
    for url, filename in NATURAL_IMAGES:
        save_path = os.path.join(NATURAL_DIR, filename)
        if os.path.exists(save_path) and os.path.getsize(save_path) > 1000:
            print(f"  [SKIP] {filename}")
            success += 1
            continue
        ok = download_image(url, save_path)
        print(f"  [{'OK' if ok else 'FAIL'}] {filename}")
        if ok:
            success += 1
        time.sleep(0.5)
    print(f"Downloaded {success}/{len(NATURAL_IMAGES)}")


def find_cjk_font():
    for path in [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]:
        if os.path.exists(path):
            return path
    return None


def generate_document_image(content_lines, filename):
    width, height = 800, 600
    img = Image.new("RGB", (width, height), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    font_path = find_cjk_font()

    if font_path:
        try:
            title_font = ImageFont.truetype(font_path, 24)
            body_font = ImageFont.truetype(font_path, 16)
            small_font = ImageFont.truetype(font_path, 12)
        except Exception:
            title_font = body_font = small_font = ImageFont.load_default()
    else:
        title_font = body_font = small_font = ImageFont.load_default()

    y = 30
    title = content_lines[0]
    tw = draw.textlength(title, font=title_font)
    draw.text(((width - tw) / 2, y), title, fill="#000000", font=title_font)
    y += 50
    draw.line([(50, y), (width - 50, y)], fill="#CCCCCC", width=2)
    y += 20

    for line in content_lines[1:]:
        if line.startswith("---"):
            draw.line([(50, y + 10), (width - 50, y + 10)], fill="#CCCCCC", width=1)
            y += 25
        elif line.startswith("|"):
            draw.rectangle([(50, y), (width - 50, y + 25)], outline="#CCCCCC")
            draw.text((60, y + 4), line, fill="#333333", font=body_font)
            y += 28
        else:
            draw.text((60, y), line, fill="#333333", font=body_font)
            y += 25
        if y > height - 50:
            break

    draw.line([(50, height - 40), (width - 50, height - 40)], fill="#CCCCCC", width=1)
    draw.text((width // 2 - 30, height - 30), "- 1 -", fill="#999999", font=small_font)

    img.save(os.path.join(DOCUMENT_DIR, filename), "JPEG", quality=90)


def generate_all_documents():
    os.makedirs(DOCUMENT_DIR, exist_ok=True)
    print("Generating 40 document images...")

    docs = [
        ("document_001.jpg", ["年度工作报告", "", "一、总体概述", "2024年度公司实现营业收入350万元，", "同比增长15%，员工总数达到1000人。", "二、业务发展", "各业务板块均实现稳步增长。"]),
        ("document_002.jpg", ["2024年经营数据报告", "", "核心指标：", "营业收入：350万元", "增长率：15%", "员工人数：1000人", "客户满意度：92%"]),
        ("document_003.jpg", ["合作协议书", "", "甲方：ABC科技有限公司", "乙方：XYZ贸易有限公司", "合作期限：2024年1月至2025年12月", "合作内容：技术开发与市场推广"]),
        ("document_004.jpg", ["市场营销策略规划", "", "一、市场分析", "当前市场竞争日趋激烈，", "消费者需求呈现多元化趋势。", "二、策略目标", "提升品牌知名度，扩大市场份额。"]),
        ("document_005.jpg", ["项目进度报告", "", "重要日期：", "项目启动：2024年1月1日", "阶段验收：2024年6月30日", "项目结项：2024年12月31日"]),
        ("document_006.jpg", ["增值税普通发票", "", "发票代码：044001900111", "发票号码：20240101", "开票日期：2024年3月15日", "金额：5,280.00元", "税额：316.80元"]),
        ("document_007.jpg", ["数据分析报告", "", "一、数据展示", "本报告使用柱状图和饼图", "来展示各季度销售数据变化趋势。", "二、关键发现", "第一季度销售增长显著。"]),
        ("document_008.jpg", ["个人简历", "", "姓名：张伟", "学历：硕士研究生", "专业：计算机科学与技术", "技能：Python编程、数据分析、机器学习", "工作经验：3年互联网公司开发经验"]),
        ("document_009.jpg", ["研究结论报告", "", "一、研究背景", "本研究旨在分析行业发展趋势。", "二、主要结论", "建议加大研发投入，提高产品竞争力。"]),
        ("document_010.jpg", ["餐厅菜单", "", "【热菜】", "宫保鸡丁    ￥48", "红烧肉      ￥58", "清蒸鱼      ￥68", "【凉菜】", "凉拌黄瓜    ￥18", "皮蛋豆腐    ￥22"]),
        ("document_011.jpg", ["员工通讯录", "", "姓名      部门      职务", "张三      技术部    经理", "李四      市场部    主管", "王五      财务部    会计", "赵六      人事部    专员"]),
        ("document_012.jpg", ["市场分析报告", "", "报告编号：MR-2024-001", "编制部门：市场部", "报告作者：市场部经理 张明", "审核日期：2024年2月28日"]),
        ("document_013.jpg", ["销售数据统计表", "", "| 月份 | 销售额 | 增长率 |", "| 1月  | 50万   | 8%    |", "| 2月  | 55万   | 10%   |", "| 3月  | 62万   | 13%   |"]),
        ("document_014.jpg", ["求职简历", "", "姓名：李明", "毕业院校：北京大学", "专业：计算机科学", "学位：硕士", "研究方向：人工智能与机器学习"]),
        ("document_015.jpg", ["数字化转型白皮书", "", "核心观点：", "数字化转型对企业发展至关重要。", "企业应从战略层面重视数字化建设，", "将其作为核心竞争力的重要组成部分。"]),
        ("document_016.jpg", ["采购订单", "", "订单编号：PO-2024-0156", "供应商：深圳某电子有限公司", "交货日期：2024年5月15日", "交货地点：北京仓库"]),
        ("document_017.jpg", ["联系我们", "", "公司名称：北京某科技有限公司", "地址：北京市海淀区中关村大街1号", "电话：13800138000", "邮箱：example@email.com"]),
        ("document_018.jpg", ["项目文档", "", "文档编号：DOC-2024-001", "版本：V1.0", "页数：共15页", "编制日期：2024年1月", "保密级别：内部资料"]),
        ("document_019.jpg", ["合同条款", "", "第五条 保密条款", "双方对合作中获知的商业秘密", "负有保密义务，保密期为3年。", "第六条 违约责任", "任何一方违反本合同约定，", "应承担相应的违约责任。"]),
        ("document_020.jpg", ["项目提案", "", "项目名称：智能客服系统建设", "项目预算：50万元人民币", "实施周期：6个月", "预期收益：降低客服成本30%"]),
        ("document_021.jpg", ["技术方案文档", "", "一、技术架构", "采用微服务架构设计", "二、关键技术", "API接口设计规范", "数据库优化方案", "云计算资源部署"]),
        ("document_022.jpg", ["产品说明书", "", "产品名称：智能家居控制器", "文件格式：PDF文档", "适用范围：家庭自动化系统", "主要功能：灯光控制、温度调节"]),
        ("document_023.jpg", ["季度销售趋势图", "", "图表标题：2023年季度销售趋势图", "第一季度：1200万元", "第二季度：1500万元", "第三季度：1800万元", "第四季度：2100万元"]),
        ("document_024.jpg", ["软件安装说明书", "", "安装步骤：", "第一步：安装软件", "下载安装包并运行安装程序", "第二步：配置参数", "根据实际需求设置系统参数", "第三步：运行测试"]),
        ("document_025.jpg", ["公司信息", "", "公司全称：北京某科技有限公司", "注册地址：北京市海淀区中关村大街1号", "邮编：100080", "联系电话：010-12345678"]),
        ("document_026.jpg", ["产品使用手册", "", "目标受众：", "本手册面向企业管理人员和技术团队，", "帮助用户快速掌握产品使用方法。", "适用版本：V2.0及以上"]),
        ("document_027.jpg", ["运营数据报告", "", "关键指标：", "用户增长率：25%", "日活跃用户：10万", "月活跃用户：50万", "用户留存率：78%"]),
        ("document_028.jpg", ["软件版本说明", "", "产品名称：企业管理平台", "版本号：V2.1", "发布日期：2024年3月", "更新内容：优化用户界面", "新增数据导出功能"]),
        ("document_029.jpg", ["参考文献列表", "", "[1] 机器学习实战, 人民邮电出版社", "[2] 深度学习, 人民邮电出版社", "[3] Python数据分析, 机械工业出版社", "[4] 人工智能导论, 清华大学出版社"]),
        ("document_030.jpg", ["供应链优化建议", "", "主要建议：", "1. 优化供应链管理流程", "2. 降低运营成本", "3. 建立供应商评估体系", "4. 实施库存精细化管理"]),
        ("document_031.jpg", ["组织架构图", "", "公司组织架构：", "总经理办公室", "├── 市场部", "├── 技术部", "├── 财务部", "└── 人力资源部"]),
        ("document_032.jpg", ["财务审核报告", "", "文档编号：FIN-2024-003", "审核人：财务总监 李华", "审核日期：2024年3月20日", "审核意见：数据准确，符合规范"]),
        ("document_033.jpg", ["项目时间计划", "", "项目阶段安排：", "第一季度：需求分析与系统设计", "第二季度：核心功能开发", "第三季度：系统测试与优化", "第四季度：上线部署"]),
        ("document_034.jpg", ["风险评估报告", "", "主要风险识别：", "1. 技术风险：核心技术依赖外部供应商", "2. 市场风险：市场竞争加剧", "3. 资金风险：现金流压力"]),
        ("document_035.jpg", ["产品介绍", "", "产品名称：智能音箱", "售价：299元", "主要功能：支持语音控制", "内置AI助手", "兼容多种智能家居设备"]),
        ("document_036.jpg", ["执行摘要", "", "项目概述：", "本项目旨在建设企业数字化平台。", "投资规模：200万元", "预计投资回报率：30%", "预计回收期：8个月"]),
        ("document_037.jpg", ["质量管理报告", "", "质量指标：", "产品合格率：99.5%", "客户满意度：95%", "退货率：0.3%", "投诉处理时效：24小时内响应"]),
        ("document_038.jpg", ["竞争分析报告", "", "市场格局：", "主要竞争对手有三家", "市场份额分布：", "A公司：40%", "B公司：30%", "C公司：20%"]),
        ("document_039.jpg", ["财务年度报告", "", "财务数据摘要：", "年营收：5000万元", "净利润：800万元", "毛利率：35%", "资产负债率：45%"]),
        ("document_040.jpg", ["战略规划报告", "", "未来展望：", "未来三年内实现业务规模翻倍，", "进入国际市场，拓展海外业务。", "重点布局：产品研发创新、海外市场拓展"]),
    ]

    for filename, content in docs:
        save_path = os.path.join(DOCUMENT_DIR, filename)
        if os.path.exists(save_path):
            print(f"  [SKIP] {filename}")
            continue
        generate_document_image(content, filename)
        print(f"  [OK] {filename}")
    print("Document images done.")


def main():
    print("=" * 50)
    print("测试图片生成/下载工具")
    print("=" * 50)
    download_natural_scene_images()
    print()
    generate_all_documents()
    print()
    print("Done! Images saved to:", BASE_DIR)


if __name__ == "__main__":
    main()
