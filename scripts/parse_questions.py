#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公考行测 PDF 卷子 → 结构化 JSON 解析脚本

流程：
  1. 扫描 data/pdf/ 下的 PDF
  2. 用 PyMuPDF 把每页渲染成图片
  3. 逐页调用通义千问-VL（OpenAI 兼容模式），识别题目 / 答案
  4. 合并题目与答案，按题号对齐
  5. 输出 data/json/<卷子名>.json

用法：
  1. 把 PDF 卷子放到 data/pdf/ 目录
  2. 设置环境变量 DASHSCOPE_API_KEY（阿里云百炼 API Key）
  3. 运行：python scripts/parse_questions.py [卷子名.pdf]

依赖：pip install PyMuPDF requests
"""

import base64
import json
import os
import sys
import time
from pathlib import Path

import requests

# ---------- 配置 ----------
API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = os.getenv("QWEN_VL_MODEL", "qwen-vl-max")  # 可用 qwen-vl-max / qwen-vl-plus

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "data" / "pdf"
JSON_DIR = ROOT / "data" / "json"

DPI = 150  # 渲染分辨率，越高图越清晰但 token 越多
MAX_RETRY = 3
ANSWER_TAIL_PAGES = 2  # 卷子末尾几页视为答案页（行测答案通常在最后 1-2 页，可自行调整）

# ---------- Prompt ----------
QUESTION_PROMPT = """你是一名公考（公务员考试）行测题目的结构化解析专家。
请仔细识别图片中的所有行测题目，并把它们转换为严格的 JSON。

对每一道题，输出如下结构的对象：
{
  "module": "从[常识判断,言语理解,数量关系,判断推理,资料分析]中选一个",
  "subModule": "子模块名，如 图形推理/逻辑填空/定义判断/类比推理/逻辑判断/数学运算/资料分析 等",
  "stem": "题干完整文本，不包含选项",
  "optionA": "选项A内容",
  "optionB": "选项B内容",
  "optionC": "选项C内容",
  "optionD": "选项D内容",
  "analysis": "解析内容，若图中没有解析则写空字符串"
}

硬性要求：
1. 只输出一个 JSON 数组，例如：[{...},{...}]，不要输出任何解释性文字、代码块标记或前后缀。
2. 题干中的图形（如图形推理的图形、资料分析的统计图表）无法用文字准确描述时，在 stem 末尾追加占位符【此处有图】。
3. 如果图片中没有题目（例如是封面、目录、答案页、解析页），输出空数组 []。
4. 选项必须精确对位到 A/B/C/D，不要漏选或多选。
"""

ANSWER_PROMPT = """这是公考行测试卷的答案/解析页。
请识别其中的答案，输出严格的 JSON：
{"type": "answers", "answers": {"1": "A", "2": "B", "3": "C"}}
其中 key 是题号（数字字符串），value 是答案（A/B/C/D 之一）。
只输出 JSON，不要任何其他文字。若图中没有答案，输出 {"type": "answers", "answers": {}}。
"""

# ---------- 工具函数 ----------

def pdf_to_images(pdf_path: Path, dpi: int = DPI):
    """把 PDF 每页渲染为 PNG bytes 列表"""
    import pymupdf
    doc = pymupdf.open(str(pdf_path))
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=dpi)
        images.append(pix.tobytes("png"))
    doc.close()
    return images


def call_qwen_vl(image_bytes, prompt, system=None):
    """调用通义千问-VL，返回文本内容"""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ],
    })

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.1,
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    for attempt in range(MAX_RETRY):
        try:
            resp = requests.post(
                f"{BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=180,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  [warn] 第 {attempt + 1} 次调用失败: {e}")
            if attempt < MAX_RETRY - 1:
                time.sleep(3 * (attempt + 1))
            else:
                return ""


def extract_json(text):
    """从模型输出中提取 JSON（去掉可能的 ```json 标记等）"""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]
    elif text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            text = text[start:end + 1]
    return text


# ---------- 解析流程 ----------

def parse_pdf(pdf_path: Path):
    """解析单个 PDF，返回题目列表（含答案）"""
    name = pdf_path.stem
    print(f"\n=== 解析 {pdf_path.name} ===")

    images = pdf_to_images(pdf_path)
    print(f"共 {len(images)} 页，开始逐页识别...")

    questions = []      # 题目列表（无答案）
    answers = {}        # 题号 -> 答案

    for idx, img in enumerate(images, start=1):
        # 卷子末尾几页当作答案页，其余当作题目页
        is_answer_page = idx > len(images) - ANSWER_TAIL_PAGES
        prompt = ANSWER_PROMPT if is_answer_page else QUESTION_PROMPT

        raw = call_qwen_vl(img, prompt)
        if not raw:
            print(f"  [skip] 第 {idx} 页无有效返回")
            continue

        cleaned = extract_json(raw)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            print(f"  [warn] 第 {idx} 页 JSON 解析失败，原文: {raw[:80]}...")
            continue

        if isinstance(data, list):
            questions.extend(data)
            print(f"  第 {idx} 页: 识别到 {len(data)} 道题")
        elif isinstance(data, dict) and data.get("type") == "answers":
            answers.update(data.get("answers", {}))
            print(f"  第 {idx} 页: 识别到 {len(data.get('answers', {}))} 条答案")
        else:
            print(f"  第 {idx} 页: 未识别到题目或答案")

    # 合并：按顺序给题目编号，用答案映射填充
    print(f"\n识别完成: {len(questions)} 道题, {len(answers)} 条答案")
    for i, q in enumerate(questions, start=1):
        q["answer"] = answers.get(str(i), "")

    return questions


def main():
    if not API_KEY:
        print("错误：未设置 DASHSCOPE_API_KEY 环境变量")
        print("设置方法(Git Bash): export DASHSCOPE_API_KEY=sk-xxx")
        sys.exit(1)

    JSON_DIR.mkdir(parents=True, exist_ok=True)

    # 指定 PDF 则只解析该文件，否则解析目录下全部
    targets = [Path(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else sorted(PDF_DIR.glob("*.pdf"))
    targets = [p for p in targets if p.suffix.lower() == ".pdf"]

    if not targets:
        print(f"未找到 PDF，请把卷子放到 {PDF_DIR}")
        sys.exit(1)

    for pdf in targets:
        questions = parse_pdf(pdf)
        out = JSON_DIR / f"{pdf.stem}.json"
        out.write_text(
            json.dumps(questions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"已输出: {out} ({len(questions)} 道题)")


if __name__ == "__main__":
    main()
