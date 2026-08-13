#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从真题仓库 ZIP 解压指定分类的 PDF 到 data/pdf/
用法: python scripts/extract_pdfs.py 国考   (可选参数: 国考/省考以及市考/选调，默认解压国考)
"""
import os
import sys
import zipfile

ZIP = "C:/Users/MaHuhu/Downloads/AdministrativeAptitudeTest-main.zip"
BASE = "C:/Code/Java-study-item/gk-line-test/data/pdf"
PREFIX = "AdministrativeAptitudeTest-main/"

category = sys.argv[1] if len(sys.argv) > 1 else "国考"

z = zipfile.ZipFile(ZIP)
count = 0
total_size = 0
for n in z.namelist():
    # 只解压指定分类下的 PDF
    if n.startswith(PREFIX + category + "/") and n.endswith(".pdf"):
        rel = n[len(PREFIX):]
        target = os.path.join(BASE, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with z.open(n) as src, open(target, "wb") as dst:
            data = src.read()
            dst.write(data)
            total_size += len(data)
        count += 1

print(f"解压完成: {category} 共 {count} 个 PDF, 总计 {total_size / 1024 / 1024:.1f} MB")
print(f"输出目录: {BASE}/{category}/")
