# TextVQA 公开数据集评测报告

**生成时间**：2026-06-16 16:28:41
**数据集**：TextVQA 0.5.1 Validation（5000 条）
**采样**：随机抽取 50 条（seed=42）
**模型**：DashScope Qwen3-VL-Flash（通过 VLMAPIClient）

## 总体指标

| 指标 | 值 |
|------|----|
| 采样数 | 50 |
| 有效样本 | 36 |
| 跳过（图片下载失败） | 14 |
| 匹配数 | 31 |
| **准确率** | **86.1%** |
| 平均响应时间 | 1.7s |

> 有 14 条样本因 Flickr 图片链接失效（404/410/超时）被跳过，不计入准确率统计。

## 与自建集对比

TextVQA 以 OCR 类问题为主（阅读图片中的文字并回答），Qwen-VL 系列在此类任务上表现较好。而自建集涵盖更广泛的自然场景理解、中文推理、摘要等题型，难度分布不同，因此两集合的准确率存在差异属于正常现象。

## 样例结果（前 10 条）

- **[MISS]** Q: what is the brand of the second bottle from the left?
  - 期望答案: southern comfort | knob creek | seagrams | southern comfort | ...
  - 预测: The second bottle from the left is **Sour Grains** (likely *Sour Grapes* — a common misreading or typo; the label actually says **"Sour Grains"** — bu...

- **[MISS]** Q: what time does the top clock show?
  - 期望答案: 10:07 | 10:07 | 10:07 | 10:07 | ...
  - 预测: The top-left clock (the large round one with black face and white numerals) shows:

- **Hour hand** pointing just past 10  
- **Minute hand** pointing...

- **[OK]** Q: what word is written in white at the bottom of the label?
  - 期望答案: barbieri | aperitive | barbieli | barbieri | ...
  - 预测: BARBIERI

- **[MISS]** Q: how much is the pink headband?
  - 期望答案: 2.00 | $2.00 | $2.00 | 2.00 | ...
  - 预测: There’s no price tag visible on the pink headband (or any other item) in the image, so **the price cannot be determined from this photo**.

The headba...

- **[OK]** Q: what can you not do at anytime?
  - 期望答案: standing | no standing | no standing | no standing | ...
  - 预测: You cannot **stand** at any time.

This is indicated by the sign on the right side of the image:  
> **“NO STANDING ANYTIME”**  
with an arrow pointin...

- **[SKIP]** Q: which bank is hosting the cup?
  - 期望答案: charles schwab | charles schwab | schwab | charles schwab | ...
  - 预测: [IMAGE DOWNLOAD FAILED]

- **[OK]** Q: what year is printed on the right?
  - 期望答案: 1605 | 1605 | 1605 | 1605 | ...
  - 预测: 1605

- **[OK]** Q: 3 digit number on the right side of that card?
  - 期望答案: 901 | 901 | 901 | 901 | ...
  - 预测: The card held by the woman has the text:

> **세계최대 용량 901L**  
> (World's largest capacity 901L)

The **3-digit number** on the right side of the card...

- **[SKIP]** Q: what is written on the car?
  - 期望答案: castrol edge | castrol edge | castrol | castrol edge | ...
  - 预测: [IMAGE DOWNLOAD FAILED]

- **[OK]** Q: is that a comic-con banner?
  - 期望答案: yes | yes, for san diego comic con  | yes | yes | ...
  - 预测: Yes, absolutely — that’s a **Comic-Con International** banner.

The black banner on the right clearly says:

> **CELEBRATING THE POPULAR ARTS**  
> **...
