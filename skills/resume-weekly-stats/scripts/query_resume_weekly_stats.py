#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统计"岗位招聘管理文档 - 简历库"周报（JAVA + 前端岗位），并把完整报告保存为本地 Markdown 文件。

统计范围：只统计"岗位"字段含 JAVA 或 "前端" 的记录（其他岗位不统计）。
统计维度：面试官 × 岗位（JAVA / 前端 分别统计 + 小计）。
展示顺序：先汇总（岗位维度数字表 + 全部已面试候选人明细，含岗位/面试官列），后各面试官数据（每位面试官一份岗位数字表）。

时间窗口（用户口径，已确认）：
- 起点 = 当前系统时间之前最近的一个周六 00:00:00；终点 = 当前系统时间。
  - 今天是周六 -> 起点为 7 天前的周六
  - 今天是周日 -> 起点为昨天（周六）
  - 其他日子 -> 本周最近的一个周六（周一=2天前、周二=3天前、…、周五=6天前）

统计口径（4 个数字，互不排斥）：
1. 需要面试的简历数：简历添加日期 ∈ [起点, 现在]
2. 已完成面试简历数：面试时间 ∈ [起点, 现在]
3. 简历不合适数量：面试状态 ∈ {简历不合适, 联系不上} 且 面试时间 ∈ [起点, 现在]
4. 优秀简历数量：面试评级 ∈ {A（极好）, B（不错）} 且 面试时间 ∈ [起点, 现在]
   （第 1 项按"简历添加日期"，第 2/3/4 项均按"面试时间"；第 3 项含"简历不合适/联系不上"两种状态。）

已面试候选人明细（合并口径）：
- 收录：面试时间 ∈ [起点, 现在] 的记录，以及 面试状态 ∈ {简历不合适, 联系不上} 且 简历添加日期 ∈ [起点, 现在] 的记录。
- 面试评级列：简历不合适/联系不上 → 显示面试状态；否则有评级显示评级；其余"空"。
- 原因列：仅简历不合适/联系不上展示"二次沟通情况"（多行合并为单行，缺失留空）；其余留空。
- 排序：A（极好）→ B（不错）→ C（一般）→ D（未通过）→ 简历不合适/联系不上 → 空白；组内按面试时间从早到晚。

保存：完整报告打印到控制台，并写入
    G:\\Documents\\岗位\\简历库周报_{起点日期}_{今天日期}.md（UTF-8）

用法：python query_resume_weekly_stats.py
"""

import io
import json
import os
import subprocess
from collections import OrderedDict
from datetime import datetime, timedelta

BASE_TOKEN = "ILuybtceKau2X2sbLx0c4SRpnOg"
TABLE_ID = "tblLcOSapd0nUuhl"
OUTPUT_DIR = r"G:\Documents\岗位"

FIELDS = [
    "候选人姓名",       # fld7t1q8QJ
    "岗位",             # fldPVWgXor
    "简历添加日期",     # fldbxJYEP6 (created_at)
    "简历添加时间",     # fldCHAJY90 (created_at)
    "面试时间",         # fldzXgAnId (datetime)
    "面试官",           # fldv2ruekN (user)
    "面试状态",         # fldjcGWkH9 (select)
    "面试评级",         # fldZLXjLTc (select)
    "二次沟通情况",     # fldhlaGmat (text)
    "期望薪资",         # fld0kx4vuF (formula)
    "最快到岗时间",     # fldusj92Ak (formula)
]
PAGE_SIZE = 200

UNSUITABLE_STATUSES = {"简历不合适", "联系不上"}
GOOD_RATINGS = {"A（极好）", "B（不错）"}
RATING_ORDER = {"A（极好）": 0, "B（不错）": 1, "C（一般）": 2, "D（未通过）": 3}
UNSUITABLE_ORDER = {"简历不合适": 4, "联系不上": 5}

WEEKDAYS_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def compute_window_start(now):
    """最近一个严格早于 now 的周六 00:00:00。

    weekday(): 周一=0 ... 周六=5, 周日=6。
    (weekday() - 5) % 7 表示"距上一个周六过去的天数"：
    - 周六 -> 0，此时取 7（上周六）
    - 周日 -> 1（昨天即周六）
    - 周三 -> 4（4 天前即周六）
    """
    days_since_sat = (now.weekday() - 5) % 7
    if days_since_sat == 0:
        days_since_sat = 7
    return (now - timedelta(days=days_since_sat)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def parse_dt(value):
    """解析 lark-cli 返回的 ISO8601 字符串（含 +08:00 时区）。"""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def pick(row, fields, name):
    """按字段名取值；list 类型取第一个元素，user 字段取 name。"""
    for field, value in zip(fields, row):
        if field == name:
            if isinstance(value, list):
                if not value:
                    return ""
                if name == "面试官":
                    item = value[0]
                    return item.get("name", "") if isinstance(item, dict) else str(item)
                return value[0]
            return value
    return ""


def pick_interviewer(row, fields):
    """返回面试官 (id, name)；缺失返回 (None, "")。"""
    for field, value in zip(fields, row):
        if field == "面试官":
            if isinstance(value, list) and value:
                item = value[0]
                if isinstance(item, dict):
                    return item.get("id"), item.get("name", "")
                return None, str(item)
            if isinstance(value, dict):
                return value.get("id"), value.get("name", "")
            return None, str(value) if value else ""
    return None, ""


def job_category(row, fields):
    """按岗位字段判定类别：JAVA / 前端；都不含返回 None。"""
    job = str(pick(row, fields, "岗位") or "").lower()
    if "java" in job:
        return "JAVA"
    if "前端" in job:
        return "前端"
    return None


def run_record_list(filter_conditions, offset):
    cmd = [
        "lark-cli", "base", "+record-list",
        "--base-token", BASE_TOKEN,
        "--table-id", TABLE_ID,
    ]
    for fid in FIELDS:
        cmd += ["--field-id", fid]
    if filter_conditions is not None:
        cmd += ["--filter-json", json.dumps(
            {"logic": "and", "conditions": filter_conditions}, ensure_ascii=False)]
    cmd += ["--limit", str(PAGE_SIZE), "--offset", str(offset), "--format", "json", "--as", "user"]

    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError("lark-cli 查询失败：exit=%s，stderr=%s"
                           % (proc.returncode, proc.stderr))
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("无法解析 lark-cli 输出：%s\n输出：%s" % (exc, proc.stdout[:2000]))
    if not payload.get("ok"):
        raise RuntimeError("lark-cli 返回错误：%s" % json.dumps(payload.get("error"), ensure_ascii=False))
    return payload.get("data", {})


def fetch_all():
    """服务端按 面试官非空 筛选，分页拉取全量记录。"""
    conditions = [["面试官", "non_empty"]]
    all_rows, fields, offset = [], [], 0
    while True:
        data = run_record_list(conditions, offset)
        if not fields:
            fields = data.get("fields", [])
        rows = data.get("data", [])
        all_rows.extend(rows)
        if not data.get("has_more") or not rows:
            break
        offset += len(rows)
    return fields, all_rows


def compute_group(rows, fields, start, now):
    """对一组记录按统计口径计算 4 个数字 + 明细（返回 dict）。"""
    need_interview = 0
    done_interview = 0
    unsuitable = 0
    excellent = 0
    detail = []

    for row in rows:
        add_dt = parse_dt(pick(row, fields, "简历添加日期"))
        itv_dt = parse_dt(pick(row, fields, "面试时间"))
        status = str(pick(row, fields, "面试状态") or "").strip()
        rating = str(pick(row, fields, "面试评级") or "").strip()

        if add_dt and start <= add_dt <= now:
            need_interview += 1
        if itv_dt and start <= itv_dt <= now:
            done_interview += 1
            if rating in GOOD_RATINGS:
                excellent += 1
            if status in UNSUITABLE_STATUSES:
                unsuitable += 1
            detail.append(row)
        elif add_dt and start <= add_dt <= now and status in UNSUITABLE_STATUSES:
            detail.append(row)

    detail.sort(key=detail_sort_key(fields))
    return {
        "need": need_interview, "done": done_interview,
        "unsuitable": unsuitable, "excellent": excellent, "detail": detail,
    }


def detail_sort_key(fields):
    def key(row):
        rating = str(pick(row, fields, "面试评级") or "").strip()
        status = str(pick(row, fields, "面试状态") or "").strip()
        if status in UNSUITABLE_ORDER:
            rank = UNSUITABLE_ORDER[status]
        elif rating in RATING_ORDER:
            rank = RATING_ORDER[rating]
        else:
            rank = 99
        itv = parse_dt(pick(row, fields, "面试时间"))
        return (rank, 0 if itv else 1, itv or datetime.min)
    return key


def pct(done, need):
    base = need if need else 1
    return "%.1f%%" % (done * 100.0 / base)


class Reporter:
    """收集报告行（Markdown 文本），最后统一打印并写入本地 Markdown 文件。"""

    def __init__(self):
        self.lines = []

    def emit(self, s=""):
        self.lines.append(s)

    def emit_job_table(self, rows_by_job):
        """输出岗位维度数字表：JAVA / 前端 / 合计 三行。rows_by_job: {job: res_dict}"""
        header = "| 岗位 | 需要面试 | 已完成 | 已完成率 | 不合适 | 优秀(A/B) |"
        self.emit(header)
        self.emit("| --- | --- | --- | --- | --- | --- |")
        order = ["JAVA", "前端"]
        totals = {"need": 0, "done": 0, "unsuitable": 0, "excellent": 0}
        for job in order:
            res = rows_by_job.get(job, {"need": 0, "done": 0, "unsuitable": 0, "excellent": 0})
            for k in totals:
                totals[k] += res[k]
            self.emit("| %s | %d | %d | %s | %d | %d |" % (
                job, res["need"], res["done"], pct(res["done"], res["need"]),
                res["unsuitable"], res["excellent"]))
        self.emit("| **合计** | **%d** | **%d** | **%s** | **%d** | **%d** |" % (
            totals["need"], totals["done"], pct(totals["done"], totals["need"]),
            totals["unsuitable"], totals["excellent"]))
        self.emit("> 口径：已完成率 = 已完成面试数 / 需要面试数；4 个数字独立统计，占比仅供参考。")

    def emit_detail(self, detail, fields):
        """输出已面试候选人明细表（含岗位、面试官列）。"""
        if not detail:
            self.emit("（无）")
            return
        self.emit("| 序号 | 姓名 | 岗位 | 面试官 | 简历添加时间 | 面试时间 | 面试评级 | 期望薪资 | 最快到岗 | 原因 |")
        self.emit("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for i, row in enumerate(detail, 1):
            name = str(pick(row, fields, "候选人姓名")).strip()
            job = job_category(row, fields) or str(pick(row, fields, "岗位") or "").strip()
            _, iname = pick_interviewer(row, fields)
            interviewer = iname or "空"
            add_t = fmt_dt_full(parse_dt(pick(row, fields, "简历添加时间")))
            itv = fmt_dt(parse_dt(pick(row, fields, "面试时间")))
            rating_val = str(pick(row, fields, "面试评级") or "").strip()
            status = str(pick(row, fields, "面试状态") or "").strip()
            if status in UNSUITABLE_STATUSES:
                rating_disp = status
                reason = " ".join(str(pick(row, fields, "二次沟通情况") or "").strip().split())
            elif rating_val:
                rating_disp = rating_val
                reason = ""
            else:
                rating_disp = "空"
                reason = ""
            salary = str(pick(row, fields, "期望薪资") or "").strip() or "空"
            earliest = str(pick(row, fields, "最快到岗时间") or "").strip() or "空"
            self.emit("| %d | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                i, name, job, interviewer, add_t, itv, rating_disp, salary, earliest, reason))

    def text(self):
        return "\n".join(self.lines)


def fmt_dt(dt):
    return dt.strftime("%Y-%m-%d") if dt else "空"


def fmt_dt_full(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "空"


def main():
    now = datetime.now().astimezone()
    start = compute_window_start(now)

    fields, rows = fetch_all()

    # 只保留 JAVA / 前端 岗位的记录
    filtered = []
    for row in rows:
        if job_category(row, fields) is not None:
            filtered.append(row)

    rep = Reporter()
    start_label = "%s（%s）" % (start.strftime("%Y-%m-%d"), WEEKDAYS_CN[start.weekday()])
    now_label = "%s（%s）" % (now.strftime("%Y-%m-%d"), WEEKDAYS_CN[now.weekday()])
    rep.emit("# 简历库周报")
    rep.emit()
    rep.emit("**统计周期**：%s 00:00 至 %s 现在" % (start_label, now_label))
    rep.emit("**统计范围**：JAVA、前端岗位（按面试官×岗位统计，其他岗位不统计）")
    rep.emit()

    # ---------- 一、汇总 ----------
    rep.emit("## 一、汇总")
    rep.emit()
    summary = {}
    for job in ("JAVA", "前端"):
        summary[job] = compute_group(
            [r for r in filtered if job_category(r, fields) == job], fields, start, now)
    summary["合计"] = compute_group(filtered, fields, start, now)
    rep.emit("### 各岗位汇总")
    rep.emit()
    rep.emit_job_table(summary)
    rep.emit()

    rep.emit("### 已面试候选人明细（全部）")
    rep.emit()
    rep.emit_detail(summary["合计"]["detail"], fields)
    rep.emit()

    # ---------- 二、各面试官数据 ----------
    rep.emit("## 二、各面试官数据")
    rep.emit()

    groups = OrderedDict()
    for row in filtered:
        iid, iname = pick_interviewer(row, fields)
        if iid is None:
            continue
        if iid not in groups:
            groups[iid] = {"name": iname or iid, "rows": []}
        groups[iid]["rows"].append(row)

    computed = {}
    for iid, g in groups.items():
        job_res = {}
        for job in ("JAVA", "前端"):
            job_res[job] = compute_group(
                [r for r in g["rows"] if job_category(r, fields) == job], fields, start, now)
        total = compute_group(g["rows"], fields, start, now)
        computed[iid] = {"job": job_res, "total": total}

    ordered_ids = sorted(
        (iid for iid in groups
         if computed[iid]["total"]["need"] or computed[iid]["total"]["done"]
         or computed[iid]["total"]["unsuitable"] or computed[iid]["total"]["excellent"]),
        key=lambda iid: (-computed[iid]["total"]["done"], groups[iid]["name"]),
    )

    if not ordered_ids:
        rep.emit("（本周无 JAVA / 前端岗位记录）")
        rep.emit()
    else:
        for iid in ordered_ids:
            g = groups[iid]
            c = computed[iid]
            rep.emit("### 面试官：%s" % (g["name"] or iid))
            rep.emit()
            rep.emit_job_table(c["job"])
            rep.emit()
            rep.emit("小计：需面试 %d · 已完成 %d（%s）· 不合适 %d · 优秀(A/B) %d" % (
                c["total"]["need"], c["total"]["done"], pct(c["total"]["done"], c["total"]["need"]),
                c["total"]["unsuitable"], c["total"]["excellent"]))
            rep.emit()

    # ---------- 输出 + 保存本地 Markdown ----------
    report = rep.text()
    print(report)

    out_path = os.path.join(
        OUTPUT_DIR,
        "简历库周报_%s_%s.md" % (start.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")),
    )
    with io.open(out_path, "w", encoding="utf-8-sig", newline="\n") as f:
        f.write(report + "\n")
    print("\n[已保存] %s" % out_path)


if __name__ == "__main__":
    main()
