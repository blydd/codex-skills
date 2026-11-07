#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合格候选人查询：按岗位名称查询“岗位招聘管理文档”多维表格。

流程：
1. 岗位名称：命令行第 1 个参数；未传时默认 “JAVA-开发工程师”。
2. “海尔岗位需求”表：取岗位名包含该岗位关键词（如 JAVA / 前端）的全部记录，列表展示
   （按“除第一列‘文本’外的其他列”输出）。
3. “简历库”表：服务端筛选 岗位 == 岗位名称 且 面试状态 == 已初试，分页拉全量。
4. 本地过滤：面试评级 != D（未通过）；简历状态-海尔 不属于 {被占用、已下架、已入职、找到工作}
   （空值保留）。
5. 排序：面试评级 A（极好）> B（不错）> C（一般）> 空；同评级内面试时间倒序（无时间排最后）。
6. 输出：岗位需求列表 + 候选人表格（12 列，含“技术评价列中的面试问题内容”）。

用法：
  python query_qualified_candidates.py                 # 默认 JAVA-开发工程师
  python query_qualified_candidates.py 前端-开发工程师   # 指定岗位名称
"""

import json
import re
import subprocess
import sys

BASE_TOKEN = "ILuybtceKau2X2sbLx0c4SRpnOg"
JOB_TABLE = "tblwoDmrLwp5SCut"      # 海尔岗位需求
RESUME_TABLE = "tblLcOSapd0nUuhl"   # 简历库

DEFAULT_POSITION = "JAVA-开发工程师"

# 海尔岗位需求：字段顺序即展示顺序（第一列“文本”为原始 JSON，按需求排除）
JOB_FIELDS = [
    "岗位",
    "级别",
    "需求团队",
    "需求人数",
    "人天单价",
    "岗位状态",
    "用人开始时间",
    "用人结束时间",
    "发布人",
    "发布时间",
    "已投递人数",
    "发布周度",
    "岗位要求",
]
JOB_FIRST_COLUMN = "文本"            # 表的第一列，展示时排除

RESUME_FIELDS = [
    "候选人姓名",     # fld7t1q8QJ
    "面试官",         # fldv2ruekN
    "面试时间",       # fldzXgAnId
    "面试评级",       # fldZLXjLTc
    "期望薪资",       # fld0kx4vuF
    "毕业时间",       # fld6qhdVMg
    "电话",           # fldl4IBTnl
    "备注",           # fld2cR4MYJ
    "目前所在地",     # fld3d5TkoG
    "籍贯",           # fldVL6r7ce
    "最快到岗时间",   # fldusj92Ak
    "技术评价",       # fld0s40dEI
    "岗位",           # fldPVWgXor
    "面试状态",       # fldjcGWkH9
    "简历状态-海尔",  # fldqBeyNxD
]

EXCLUDED_RESUME_STATUSES = {"被占用", "已下架", "已入职", "找到工作"}
EXCLUDED_RATINGS = {"D（未通过）"}
RATING_RANK = {"A（极好）": 1, "B（不错）": 2, "C（一般）": 3}

PAGE_SIZE = 200

# 技术评价里的分段标签：可带 1. / 2、 序号前缀
_LABEL_RE = re.compile(r"^\s*(?:\d{1,2}\s*[.、)．]\s*)?([^\s：:]{1,20})\s*[：:]\s*(.*)$")
# 无冒号的编号小标题（如“8.最近是否面试海尔海信”）也算分段边界，用关键词识别，避免把面试问题的编号小问截断
_NUMBERED_RE = re.compile(r"^\s*\d{1,2}\s*[.、)．]\s*(.*)$")
_SECTION_KEYS = (
    "最近是否", "是否", "目前所在地", "籍贯", "期望薪", "最快到岗", "离职状态", "当前状态",
    "沟通情况", "擅长", "技术水平", "个人意见", "姓名", "邮箱", "身份证", "学信网", "外包",
)
_QUESTION_LABELS = ("面试问题", "面试问答", "面试提问")
_FALLBACK_LABELS = ("技术水平评价", "技术评价", "个人意见")


def run_record_list(table_id, field_names, conditions, offset):
    cmd = [
        "lark-cli", "base", "+record-list",
        "--base-token", BASE_TOKEN,
        "--table-id", table_id,
    ]
    for name in field_names:
        cmd += ["--field-id", name]
    if conditions:
        cmd += ["--filter-json", json.dumps({"logic": "and", "conditions": conditions}, ensure_ascii=False)]
    cmd += ["--limit", str(PAGE_SIZE), "--offset", str(offset), "--format", "json", "--as", "user"]

    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError("lark-cli 查询失败（table=%s）：%s" % (table_id, proc.stderr.strip()[:800]))
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError("lark-cli 输出无法解析（table=%s）：%s" % (table_id, proc.stdout[:800]))
    if not payload.get("ok"):
        raise RuntimeError("lark-cli 返回错误：%s" % json.dumps(payload.get("error"), ensure_ascii=False))
    return payload.get("data", {})


def fetch_all(table_id, field_names, conditions=None):
    """分页拉全量，返回 (fields, rows)。"""
    all_rows, fields, offset = [], [], 0
    while True:
        data = run_record_list(table_id, field_names, conditions, offset)
        if not fields:
            fields = data.get("fields", [])
        rows = data.get("data", [])
        all_rows.extend(rows)
        if not data.get("has_more") or not rows:
            break
        offset += len(rows)
    return fields, all_rows


def render(value):
    """单元格取值：user/select/attachment/link 等数组转成可读文本。"""
    if value is None:
        return ""
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(str(item.get("name") or item.get("text") or ""))
            else:
                parts.append(str(item))
        return "、".join(p.strip() for p in parts if p and p.strip())
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value)


def pick(row, fields, name):
    for field, value in zip(fields, row):
        if field == name:
            return value
    return None


def text_of(row, fields, name):
    return render(pick(row, fields, name))


def _is_boundary(line):
    """判断该行是否是技术评价中的下一个分段（标签带冒号，或无冒号的编号小标题）。"""
    if _LABEL_RE.match(line):
        return True
    m = _NUMBERED_RE.match(line)
    if m:
        head = m.group(1).strip()
        return any(k in head[:14] for k in _SECTION_KEYS)
    return False


def section(text, labels):
    """从“技术评价”自由文本里取出指定标签段落，返回 (命中标签, 内容)。"""
    lines = str(text or "").splitlines()
    for target in labels:
        for i, line in enumerate(lines):
            m = _LABEL_RE.match(line)
            if not m or target not in m.group(1):
                continue
            chunks = [m.group(2).strip()]
            for nxt in lines[i + 1:]:
                if _is_boundary(nxt):
                    break
                if nxt.strip():
                    chunks.append(nxt.strip())
            body = " ".join(c for c in chunks if c).strip()
            if body:
                return target, body
    return "", ""


def tech_question(row, fields):
    """技术评价列中的面试问题内容；无面试问题段时退回技术水平评价/技术评价段，并标注来源。"""
    raw = text_of(row, fields, "技术评价")
    label, body = section(raw, _QUESTION_LABELS)
    if body:
        return body
    label, body = section(raw, _FALLBACK_LABELS)
    if body:
        return "（%s）%s" % (label, body)
    return ""


def parse_time(value):
    """面试时间统一输出日期（YYYY-MM-DD），兼容 ISO 带时分秒的写法。"""
    s = str(value or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return "%s-%s-%s" % m.groups()
    return s[:10]


def time_key(value):
    """排序用时间戳：无值返回 None，供排在最后。"""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?", str(value or ""))
    if not m:
        return None
    return tuple(int(x) if x else 0 for x in m.groups())


def cell(value):
    s = render(value).replace("\r", " ").replace("\n", "；")
    return s.replace("|", "｜").strip()


def position_keyword(position):
    """岗位名称 -> 岗位需求表里的匹配关键词：取破折号前的部分。"""
    p = position.strip()
    for sep in ("-", "－", "—"):
        if sep in p:
            head = p.split(sep)[0].strip()
            if head:
                return head
    return p


def main():
    position = sys.argv[1].strip() if len(sys.argv) > 1 and sys.argv[1].strip() else DEFAULT_POSITION
    keyword = position_keyword(position)

    # 1. 海尔岗位需求：岗位名包含关键词的全部记录
    job_fields, job_rows = fetch_all(JOB_TABLE, JOB_FIELDS)
    matched_jobs = [
        row for row in job_rows
        if keyword.lower() in text_of(row, job_fields, "岗位").lower()
    ]

    open_cnt = sum(1 for r in matched_jobs if text_of(r, job_fields, "岗位状态") == "招聘中")
    print("## 一、岗位需求：%s（海尔岗位需求表中含「%s」的岗位，共 %d 条：招聘中 %d 条、其他状态 %d 条）\n" % (
        position, keyword, len(matched_jobs), open_cnt, len(matched_jobs) - open_cnt))
    if not matched_jobs:
        print("未在“海尔岗位需求”表中找到含「%s」的岗位记录。\n" % keyword)
    else:
        # 招聘中的排在前面，同状态按发布时间倒序
        matched_jobs.sort(key=lambda r: (
            0 if text_of(r, job_fields, "岗位状态") == "招聘中" else 1,
            tuple(-x for x in time_key(text_of(r, job_fields, "发布时间")) or (0, 0, 0, 0, 0)),
        ))
        headers = ["序号"] + [n for n in JOB_FIELDS if n != JOB_FIRST_COLUMN]
        print("| " + " | ".join(headers) + " |")
        print("|" + "|".join([" --- "] * len(headers)) + "|")
        for idx, row in enumerate(matched_jobs, 1):
            vals = [str(idx)]
            for name in headers[1:]:
                v = text_of(row, job_fields, name)
                vals.append(cell(v) if v else "空")
            print("| " + " | ".join(vals) + " |")
        print()

    # 2. 简历库：岗位 == 岗位名称 且 面试状态 == 已初试
    resume_fields, resume_rows = fetch_all(
        RESUME_TABLE,
        RESUME_FIELDS,
        [["岗位", "==", position], ["面试状态", "==", "已初试"]],
    )

    # 3. 本地过滤
    kept = []
    for row in resume_rows:
        rating = text_of(row, resume_fields, "面试评级")
        status = text_of(row, resume_fields, "简历状态-海尔")
        if rating in EXCLUDED_RATINGS:
            continue
        if status in EXCLUDED_RESUME_STATUSES:
            continue
        kept.append(row)

    # 4. 排序：评级 A>B>C>空，同级面试时间倒序
    def sort_key(row):
        rating = text_of(row, resume_fields, "面试评级")
        tk = time_key(text_of(row, resume_fields, "面试时间"))
        if tk is None:
            t_missing, t_val = 1, (0, 0, 0, 0, 0)
        else:
            t_missing, t_val = 0, tk
        return (RATING_RANK.get(rating, 9), t_missing, tuple(-x for x in t_val))

    kept.sort(key=sort_key)

    dist = {"A（极好）": 0, "B（不错）": 0, "C（一般）": 0, "未评级": 0}
    for row in kept:
        rating = text_of(row, resume_fields, "面试评级")
        dist[rating if rating in dist else "未评级"] += 1

    print("## 二、合格候选人（岗位=%s｜面试状态=已初试｜评级≠D｜简历状态-海尔 不含 被占用/已下架/已入职/找到工作）\n" % position)
    print("共 %d 人：A（极好）%d 人、B（不错）%d 人、C（一般）%d 人、未评级 %d 人。\n" % (
        len(kept), dist["A（极好）"], dist["B（不错）"], dist["C（一般）"], dist["未评级"]))

    if not kept:
        print("未查询到满足条件的候选人。")
        return

    header = ["候选人姓名", "面试官", "面试时间", "面试评级", "期望薪资", "毕业时间", "电话", "备注",
              "目前所在地", "籍贯", "最快到岗时间", "技术评价-面试问题"]
    print("| " + " | ".join(header) + " |")
    print("|" + "|".join([" --- "] * len(header)) + "|")
    for row in kept:
        values = [
            cell(text_of(row, resume_fields, "候选人姓名")),
            cell(text_of(row, resume_fields, "面试官")),
            cell(parse_time(pick(row, resume_fields, "面试时间"))),
            cell(text_of(row, resume_fields, "面试评级")) or "未评级",
            cell(text_of(row, resume_fields, "期望薪资")),
            cell(text_of(row, resume_fields, "毕业时间")),
            cell(text_of(row, resume_fields, "电话")),
            cell(text_of(row, resume_fields, "备注")),
            cell(text_of(row, resume_fields, "目前所在地")),
            cell(text_of(row, resume_fields, "籍贯")),
            cell(text_of(row, resume_fields, "最快到岗时间")),
            cell(tech_question(row, resume_fields)) or "无面试问题记录",
        ]
        print("| " + " | ".join(values) + " |")


if __name__ == "__main__":
    main()
