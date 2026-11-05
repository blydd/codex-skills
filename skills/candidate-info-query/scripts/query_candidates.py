#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询"岗位招聘管理文档 - 简历库"中的候选人，并按指定格式输出文本。

【指定姓名时】不加任何筛选条件，全表分页拉取后按姓名精确匹配。
  （即：不限面试状态/面试官/岗位/简历状态，优先按姓名找到人。）

【不指定姓名时】列出全部满足以下条件的候选人：
  1. 面试状态 == 已初试
  2. 面试官 == 薄国通
  3. 岗位 == JAVA-开发工程师
  4. 简历状态-海尔 不属于 {被占用、已入职、找到工作}（空值也保留）

用法：
  python query_candidates.py                 # 不带姓名，列出全部待跟进候选人
  python query_candidates.py 姓名1 [姓名2 ...]  # 指定姓名，全表按姓名匹配

输出格式（每人）：
  姓名：<候选人姓名，去首尾空白>
  岗位：JAVA-开发工程师
  级别：<面试评级 == "A（极好）" 时写"资深"，其他写"高级">
  面试时间1：
  面试时间2：
  最快到岗日期：<最快到岗时间列值>
  期望薪资：<期望薪资列值>
"""

import json
import subprocess
import sys
import unicodedata

# 异体字/康熙部首/兼容字 -> 常用字 映射（按需补充；遇到新的异体字在此加一行）
_VARIANT_MAP = {
    "\u2ef0": "\u9f99",  # ⻰(康熙部首龙) -> 龙
}


def normalize_name(name):
    """姓名归一化：去首尾空白 + NFKC + 异体字映射，用于跨异体字精确匹配。"""
    s = str(name or "").strip()
    s = unicodedata.normalize("NFKC", s)
    for k, v in _VARIANT_MAP.items():
        s = s.replace(k, v)
    return s

BASE_TOKEN = "ILuybtceKau2X2sbLx0c4SRpnOg"
TABLE_ID = "tblLcOSapd0nUuhl"
INTERVIEWER_ID = "ou_a6df4a62c68f7ae95f3d5df0dbcb5640"  # 薄国通
INTERVIEWER_NAME = "薄国通"

# 不带姓名查询时的基础条件（宽松口径，简历状态在 Python 侧过滤）
BASE_CONDITIONS = [
    ["面试状态", "==", "已初试"],
    ["面试官", "==", [{"id": INTERVIEWER_ID, "name": INTERVIEWER_NAME}]],
    ["岗位", "==", "JAVA-开发工程师"],
]

# 不带姓名查询时，简历状态-海尔 为以下值的记录排除掉
EXCLUDED_RESUME_STATUSES = {"被占用", "已入职", "找到工作"}

FIELD_IDS = [
    "候选人姓名",
    "岗位",
    "面试状态",
    "面试官",
    "简历状态-海尔",
    "面试评级",
    "最快到岗时间",
    "期望薪资",
]

PAGE_SIZE = 200


def _run_lark_cli(filter_json, offset):
    """执行单次 lark-cli 查询，返回 data dict。"""
    cmd = [
        "lark-cli",
        "base",
        "+record-list",
        "--base-token",
        BASE_TOKEN,
        "--table-id",
        TABLE_ID,
    ]
    for fid in FIELD_IDS:
        cmd += ["--field-id", fid]
    if filter_json is not None:
        cmd += ["--filter-json", filter_json]
    cmd += ["--limit", str(PAGE_SIZE), "--offset", str(offset), "--format", "json"]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "lark-cli 查询失败，exit=%s，stderr=%s" % (proc.returncode, proc.stderr)
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("无法解析 lark-cli 输出：%s\n输出：%s" % (exc, proc.stdout[:2000]))
    if not payload.get("ok"):
        raise RuntimeError("lark-cli 返回错误：%s" % json.dumps(payload.get("error"), ensure_ascii=False))
    return payload.get("data", {})


def query_records(conditions):
    """分页查询记录，返回 (fields, rows)。conditions=None 表示不加筛选条件。"""
    filter_json = None
    if conditions is not None:
        filter_json = json.dumps(
            {"logic": "and", "conditions": conditions},
            ensure_ascii=False,
        )

    all_rows = []
    fields = []
    offset = 0
    while True:
        data = _run_lark_cli(filter_json, offset)
        if not fields:
            fields = data.get("fields", [])
        rows = data.get("data", [])
        all_rows.extend(rows)
        if not data.get("has_more") or not rows:
            break
        offset += len(rows)
    return fields, all_rows


def pick(row, fields, name):
    """按字段名取值；select/user 类型取数组第一个元素，user 取 name。"""
    for field, value in zip(fields, row):
        if field == name:
            if isinstance(value, list):
                if not value:
                    return ""
                if field == "面试官":
                    item = value[0]
                    return item.get("name", "") if isinstance(item, dict) else str(item)
                return value[0]
            return value
    return ""


def to_level(grade):
    """面试评级 -> 级别：A（极好）-> 资深，其他 -> 高级。"""
    grade = str(grade or "").strip()
    if grade.startswith("A"):
        return "资深"
    return "高级"


def format_one(row, fields):
    name = str(pick(row, fields, "候选人姓名")).strip()
    earliest = pick(row, fields, "最快到岗时间")
    salary = pick(row, fields, "期望薪资")
    grade = pick(row, fields, "面试评级")
    lines = [
        "姓名：%s" % name,
        "岗位：JAVA-开发工程师",
        "级别：%s" % to_level(grade),
        "面试时间1：",
        "面试时间2：",
        "最快到岗日期：%s" % (earliest if earliest is not None else ""),
        "期望薪资：%s" % (salary if salary is not None else ""),
    ]
    return "\n".join(lines)


def main():
    args = [n.strip() for n in sys.argv[1:] if n and n.strip()]

    if not args:
        # 未提供姓名：宽松口径，排除简历状态为被占用/已入职/找到工作
        fields, rows = query_records(BASE_CONDITIONS)
        kept = []
        for row in rows:
            status = str(pick(row, fields, "简历状态-海尔") or "").strip()
            if status in EXCLUDED_RESUME_STATUSES:
                continue
            kept.append(row)
        if not kept:
            print("未查询到任何满足条件的候选人。")
            return
        blocks = [format_one(row, fields) for row in kept]
        print("\n\n".join(blocks))
        return

    # 指定姓名：不加筛选条件，全表按姓名精确匹配（归一化后匹配，兼容异体字）
    names = args
    fields, rows = query_records(None)

    matched = {}
    for row in rows:
        candidate = normalize_name(pick(row, fields, "候选人姓名"))
        matched[candidate] = row

    blocks = []
    not_found = []
    for name in names:
        key = normalize_name(name)
        if key in matched:
            blocks.append(format_one(matched[key], fields))
        else:
            not_found.append(name)

    if blocks:
        print("\n\n".join(blocks))
    if not_found:
        for name in not_found:
            print("未找到满足条件的候选人：%s" % name)
    if not blocks and not not_found:
        print("未查询到任何满足条件的候选人。")


if __name__ == "__main__":
    main()
