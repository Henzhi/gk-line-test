#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公考行测 PDF 卷子 → 结构化 JSON 解析脚本（v2，支持试卷/答案分开的结构）

目录约定（来自真题仓库解压结果）：
  data/pdf/<分类>/试卷/XXX.pdf     # 试卷（题干+选项）
  data/pdf/<分类>/答案/XXX答案.pdf  # 答案+解析

流程：
  1. 配对「试卷/答案」（按规范化后的文件名匹配）
  2. 试卷逐页调通义千问-VL 提取题目
  3. 答案逐页调通义千问-VL 提取答案映射（分模块）
  4. 按模块+顺序合并答案到题目
  5. 输出 data/json/<分类>/<卷子名>.json

用法：
  export DASHSCOPE_API_KEY=sk-xxx
  python scripts/parse_questions.py 国考            # 解析整个分类
  python scripts/parse_questions.py 国考 2024国考... # 解析单个卷子（模糊匹配）
"""

import base64
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

# ---------- 加载本地 .env（不提交 git） ----------
def _load_env():
    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

_load_env()

# ---------- 配置 ----------
API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
MODEL = os.getenv("QWEN_VL_MODEL", "qwen3.7-flash")

ROOT = Path(__file__).resolve().parent.parent
PDF_ROOT = ROOT / "data" / "pdf"
JSON_ROOT = ROOT / "data" / "json"

DPI = 150
MAX_RETRY = 3

# ---------- Prompt ----------
QUESTION_PROMPT = """你是公考行测题目的结构化解析专家。请识别图片中的所有行测题目，转换为严格 JSON 数组。

每道题输出：
{
  "module": "从[常识判断,言语理解,数量关系,判断推理,资料分析]中选一个",
  "subModule": "子模块名，如 图形推理/逻辑填空/定义判断/类比推理/逻辑判断/数学运算/资料分析",
  "stem": "题干完整文本，不含选项",
  "optionA": "选项A内容",
  "optionB": "选项B内容",
  "optionC": "选项C内容",
  "optionD": "选项D内容"
}

硬性要求：
1. 只输出一个 JSON 数组 [{...},{...}]，不要任何解释文字、代码块标记。
2. 题干中的图形（图形推理的图、资料分析图表）无法用文字描述时，在 stem 末尾加占位符【此处有图】。
3. 图片中没有题目时输出空数组 []。
4. 选项精确对位 A/B/C/D。
"""

ANSWER_PROMPT = """这是公考行测试卷的答案页。请识别答案，输出严格 JSON：
{"常识判断": {"1": "A", "2": "B"}, "言语理解": {"1": "C"}}
结构为：外层 key 是模块名（常识判断/言语理解/数量关系/判断推理/资料分析），内层 key 是题号（字符串），value 是答案（A/B/C/D）。
只输出 JSON，不要其他文字。若某模块题号连续范围如"1-20 全选B"，请展开为逐题。"""

# ---------- 工具 ----------

def pdf_to_images(pdf_path: Path, dpi: int = DPI):
    import pymupdf
    doc = pymupdf.open(str(pdf_path))
    images = [page.get_pixmap(dpi=dpi).tobytes("png") for page in doc]
    doc.close()
    return images


def call_qwen_vl(image_bytes, prompt):
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "model": MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        }],
        "temperature": 0.1,
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    for attempt in range(MAX_RETRY):
        try:
            r = requests.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload, timeout=180)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"    [warn] 第{attempt + 1}次调用失败: {e}")
            if attempt < MAX_RETRY - 1:
                time.sleep(3 * (attempt + 1))
    return ""


def extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    for opener, closer in (("[", "]"), ("{", "}")):
        s, e = text.find(opener), text.rfind(closer)
        if s != -1 and e > s:
            return text[s:e + 1]
    return text


def extract_key(name):
    """提取配对键：年份 + 卷型（应对「网友回忆版」「真题」「答案及解析」等命名变体）"""
    year = ""
    m = re.search(r"(20\d{2})", name)
    if m:
        year = m.group(1)
    vol = ""
    if "行政执法" in name:
        vol = "行政执法"
    elif "副省级" in name or "省级" in name:
        vol = "副省级"
    elif "地市级" in name or "市地级" in name:
        vol = "地市级"
    elif "A卷" in name:
        vol = "A卷"
    elif "B卷" in name:
        vol = "B卷"
    if not vol:
        m2 = re.search(r"[（(]([一二三四五六七八九十])[）)]", name)
        if m2:
            vol = "卷" + m2.group(1)
    return year + vol


# ---------- 配对 ----------

def match_papers(category_dir: Path):
    """配对试卷与答案，返回 [(paper_path, answer_path)]"""
    paper_dir = category_dir / "试卷"
    answer_dir = category_dir / "答案"
    papers = sorted(paper_dir.glob("*.pdf"))
    answers = sorted(answer_dir.glob("*.pdf"))

    answer_map = {extract_key(a.stem): a for a in answers}
    pairs = []
    unmatched = []
    for p in papers:
        key = extract_key(p.stem)
        if key in answer_map:
            pairs.append((p, answer_map[key]))
        else:
            unmatched.append(p)
    if unmatched:
        print(f"  [warn] {len(unmatched)} 个试卷未匹配到答案: {[p.stem for p in unmatched]}")
    return pairs


# ---------- 解析 ----------

def parse_questions(pdf_path: Path):
    """试卷 → 题目列表"""
    images = pdf_to_images(pdf_path)
    questions = []
    for i, img in enumerate(images, 1):
        raw = call_qwen_vl(img, QUESTION_PROMPT)
        if not raw:
            continue
        try:
            data = json.loads(extract_json(raw))
        except json.JSONDecodeError:
            print(f"    [warn] 第{i}页 JSON 解析失败")
            continue
        if isinstance(data, list):
            questions.extend(data)
        print(f"    第{i}/{len(images)}页: +{len(data) if isinstance(data, list) else 0}题")
    return questions


def parse_answers(pdf_path: Path):
    """答案 → {模块: {题号: 答案}}"""
    images = pdf_to_images(pdf_path)
    answers = {}
    for i, img in enumerate(images, 1):
        raw = call_qwen_vl(img, ANSWER_PROMPT)
        if not raw:
            continue
        try:
            data = json.loads(extract_json(raw))
        except json.JSONDecodeError:
            print(f"    [warn] 第{i}页答案 JSON 解析失败")
            continue
        if isinstance(data, dict):
            for module, mapping in data.items():
                if isinstance(mapping, dict):
                    answers.setdefault(module, {}).update(mapping)
    return answers


def merge(questions, answers):
    """按模块分组，组内按顺序编号，填充答案"""
    order = []
    for i, q in enumerate(questions, 1):
        module = q.get("module", "未知")
        mapping = answers.get(module, {})
        # 该模块已出现的题目数 + 1
        seq = sum(1 for x in questions[:i] if x.get("module") == module)
        q["answer"] = mapping.get(str(seq), "")
        order.append((module, seq))
    return questions


# ---------- 主流程 ----------

def parse_one(category: str, filter_word: str = None):
    category_dir = PDF_ROOT / category
    if not category_dir.exists():
        print(f"未找到目录 {category_dir}")
        return
    pairs = match_papers(category_dir)
    print(f"{category}: 配对到 {len(pairs)} 套卷子")

    out_dir = JSON_ROOT / category
    out_dir.mkdir(parents=True, exist_ok=True)

    for paper, answer in pairs:
        if filter_word and filter_word not in paper.name:
            continue
        print(f"\n=== {paper.name} ===")
        print("解析题目...")
        questions = parse_questions(paper)
        print("解析答案...")
        answers = parse_answers(answer)
        questions = merge(questions, answers)
        out = out_dir / f"{paper.stem}.json"
        out.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"输出 {out} ({len(questions)} 题, 有答案 {sum(1 for q in questions if q.get('answer'))} 题)")


def main():
    if not API_KEY:
        print("错误：未设置 DASHSCOPE_API_KEY 环境变量")
        print("Git Bash: export DASHSCOPE_API_KEY=sk-xxx")
        sys.exit(1)

    category = sys.argv[1] if len(sys.argv) > 1 else "国考"
    filter_word = sys.argv[2] if len(sys.argv) > 2 else None
    parse_one(category, filter_word)


if __name__ == "__main__":
    main()
