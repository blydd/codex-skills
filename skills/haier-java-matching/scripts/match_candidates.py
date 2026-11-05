#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
海尔JAVA岗位候选人匹配：每次执行实时读取“岗位招聘管理文档”最新内容。

流程：
1. 海尔岗位需求表：岗位状态=招聘中 且 岗位含 JAVA -> 岗位清单与岗位要求。
2. 简历库：岗位=JAVA-开发工程师 且 面试状态=已初试（服务端筛选，分页拉全量）。
3. 本地过滤：面试评级 != D（未通过）；简历状态-海尔 in {已录入, 空}；二次沟通情况不含“不行”。
4. 匹配排序（每个岗位独立计算，优先级从高到低）：
   a) 技术栈匹配度：岗位要求中的技术关键词 命中 候选人技术评价（擅长技术栈/面试问题/技术水平评价）的数量
   b) 面试时间距离现在越近越优先（缺失排最后）
   c) 面试评级：A（极好）> B（不错）> C（一般）> 空
   d) 期望薪资越低越好（取数值下限，缺失排最后）
5. 去重：按海尔岗位需求记录顺序逐岗位分配，每个岗位取剩余候选人池中前5，已入选者不重复参与。

用法：python match_candidates.py
"""

import json
import re
import subprocess
from datetime import datetime

BASE_TOKEN = "ILuybtceKau2X2sbLx0c4SRpnOg"

HAIER_JOB_TABLE = "tblwoDmrLwp5SCut"          # 海尔岗位需求
HAIER_JOB_FIELDS = [
    "岗位",          # fldxy6cUNO
    "岗位要求",      # fldDgxKAQb
    "岗位状态",      # flds7kGKZS
    "需求团队",      # fldXVIloBS
    "级别",          # fld2ZGEQgU
    "需求人数",      # fldQhi94iW
    "人天单价",      # fldn0rmQFv
]

RESUME_TABLE = "tblLcOSapd0nUuhl"             # 简历库
RESUME_FIELDS = [
    "候选人姓名",    # fld7t1q8QJ
    "岗位",          # fldPVWgXor
    "面试状态",      # fldjcGWkH9
    "面试评级",      # fldZLXjLTc
    "简历状态-海尔",  # fldqBeyNxD
    "二次沟通情况",   # fldhlaGmat
    "技术评价",      # fld0s40dEI
    "期望薪资",      # fld0kx4vuF
    "最快到岗时间",   # fldusj92Ak
    "面试官",        # fldv2ruekN
    "面试时间",      # fldzXgAnId
    "籍贯",          # fldVL6r7ce
    "目前所在地",     # fld3d5TkoG
]

PAGE_SIZE = 200
RATING_RANK = {"A（极好）": 1, "B（不错）": 2, "C（一般）": 3}
TOPN = 5

# 技术关键词字典：word 类为英文词边界匹配（大小写不敏感），sub 类为包含匹配（中文/带空格的英文组合）
_WORD_TERMS = [
    "java", "spring", "springboot", "springcloud", "springmvc", "mybatis", "hibernate",
    "mysql", "oracle", "pgsql", "postgresql", "sqlserver", "gbase", "redis",
    "kafka", "rocketmq", "rabbitmq", "activemq", "python", "docker", "kubernetes", "k8s",
    "elasticsearch", "es", "nacos", "dubbo", "jvm", "sql", "git", "maven", "jenkins",
    "sap", "ddd", "rag", "sse", "ai", "tm1", "kylin", "doris", "erp", "wms", "tms",
    "essbase", "feign", "seata", "canal", "gc", "linux", "hadoop", "vue", "nginx",
    "etl", "bi", "olap", "api", "restful", "devops", "sonarqube", "arthas", "skywalking",
    "oauth", "memcached", "zookeeper", "thymeleaf", "javascript", "nodejs", "redis",
]
_WORD_TERMS = list(dict.fromkeys(_WORD_TERMS))  # 去重保序

_SUB_TERMS = [
    "spring boot", "spring cloud", "spring mvc", "spring security", "spring全家桶",
    "消息中间件", "微服务", "分布式事务", "分布式", "高并发", "并发控制",
    "数据库调优", "数据结构", "多线程", "线程池", "内存管理", "垃圾回收", "设计模式",
    "单元测试", "低代码", "前后端", "运维", "架构", "秒杀", "幂等", "降级", "熔断",
    "分库分表", "索引优化", "慢查询", "缓存", "大模型", "智能体", "多智能体",
    "财务", "预算", "物流", "跨境", "网络货运", "银行", "支付", "移动端", "接口",
    "锁机制", "容器编排", "本科", "专科", "带团队", "项目负责人", "架构师",
    "线上问题排查", "高可用", "弹性扩展", "中间件",
]
_SUB_TERMS = list(dict.fromkeys(_SUB_TERMS))


def _compile_terms():
    patterns = []
    for t in _WORD_TERMS:
        # 用 ASCII 字母前后否定断言替代 \b：中英文混排时（如“JAVA项目”“java架构师”）\b 会失效
        patterns.append((t, re.compile(r"(?<![A-Za-z])" + re.escape(t) + r"(?![A-Za-z])", re.IGNORECASE)))
    for t in _SUB_TERMS:
        patterns.append((t, re.compile(re.escape(t), re.IGNORECASE)))
    return patterns


TERM_PATTERNS = _compile_terms()


def match_terms(text):
    """返回文本中命中的技术关键词标签集合。"""
    s = str(text or "")
    if not s:
        return set()
    return {label for label, pat in TERM_PATTERNS if pat.search(s)}


def run_record_list(table_id, field_ids, filter_conditions, offset):
    cmd = [
        "lark-cli", "base", "+record-list",
        "--base-token", BASE_TOKEN,
        "--table-id", table_id,
    ]
    for fid in field_ids:
        cmd += ["--field-id", fid]
    if filter_conditions is not None:
        cmd += ["--filter-json", json.dumps({"logic": "and", "conditions": filter_conditions}, ensure_ascii=False)]
    cmd += ["--limit", str(PAGE_SIZE), "--offset", str(offset), "--format", "json", "--as", "user"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError("lark-cli 查询失败：%s" % proc.stderr)
    payload = json.loads(proc.stdout)
    if not payload.get("ok"):
        raise RuntimeError("lark-cli 返回错误：%s" % json.dumps(payload.get("error"), ensure_ascii=False))
    return payload.get("data", {})


def fetch_all(table_id, field_ids, filter_conditions):
    all_rows, fields, offset = [], [], 0
    while True:
        data = run_record_list(table_id, field_ids, filter_conditions, offset)
        if not fields:
            fields = data.get("fields", [])
        rows = data.get("data", [])
        all_rows.extend(rows)
        if not data.get("has_more") or not rows:
            break
        offset += len(rows)
    return fields, all_rows


def pick(row, fields, name):
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


def parse_salary(text):
    s = str(text or "")
    m = re.search(r"期望\s*[:：]?\s*(\d+(?:\.\d+)?)", s)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    return float(m.group(1)) if m else None


def parse_time(text):
    s = str(text or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def fit_score(candidate_text, position_terms, position_level):
    """匹配得分 = 岗位要求关键词 命中 候选人技术评价 的数量 + 级别加成。"""
    cand_hits = match_terms(candidate_text)
    score = len(position_terms & cand_hits)
    level = str(position_level or "").strip()
    cand = str(candidate_text or "")
    if level == "资深" and "资深" in cand:
        score += 1
    elif level == "高级" and ("高级" in cand or "资深" in cand):
        score += 1
    return score


def position_sort_key(row, fields, position_terms, position_level):
    cand_text = pick(row, fields, "技术评价")
    fit = fit_score(cand_text, position_terms, position_level)
    dt = parse_time(pick(row, fields, "面试时间"))
    has_date = 1 if dt is not None else 0
    ts = dt.timestamp() if dt is not None else 0
    rating = str(pick(row, fields, "面试评级") or "").strip()
    rk = RATING_RANK.get(rating, 99)
    sal = parse_salary(pick(row, fields, "期望薪资"))
    sk = sal if sal is not None else float("inf")
    return (-fit, 0 if has_date else 1, -ts, rk, sk)


def fmt_candidate(row, fields):
    name = str(pick(row, fields, "候选人姓名")).strip()
    rating = str(pick(row, fields, "面试评级") or "").strip()
    rating_short = rating[0] if rating else "无"
    salary = str(pick(row, fields, "期望薪资") or "").strip()
    salary_short = salary if salary else "未填"
    dt = parse_time(pick(row, fields, "面试时间"))
    date_short = dt.strftime("%m-%d") if dt else "无"
    return "%s(%s·%s·%s)" % (name, rating_short, salary_short, date_short)


def main():
    # 1. 海尔岗位需求：招聘中 且 岗位含 JAVA
    job_fields, job_rows = fetch_all(
        HAIER_JOB_TABLE, HAIER_JOB_FIELDS,
        [["岗位状态", "==", "招聘中"], ["岗位", "intersects", "JAVA"]],
    )
    if not job_rows:
        print("未查询到招聘中含 JAVA 的海尔岗位需求。")
        return

    # 2. 简历库：岗位=JAVA-开发工程师 且 面试状态=已初试
    resume_fields, resume_rows = fetch_all(
        RESUME_TABLE, RESUME_FIELDS,
        [["岗位", "==", "JAVA-开发工程师"], ["面试状态", "==", "已初试"]],
    )

    # 3. 本地过滤
    pool = []
    for row in resume_rows:
        rating = str(pick(row, resume_fields, "面试评级") or "").strip()
        resume_status = str(pick(row, resume_fields, "简历状态-海尔") or "").strip()
        second_talk = str(pick(row, resume_fields, "二次沟通情况") or "").strip()
        if rating == "D（未通过）":
            continue
        if resume_status not in ("已录入", ""):
            continue
        if "不行" in second_talk:
            continue
        pool.append(row)

    # 4. 逐岗位分配（去重：已入选者不再参与后续岗位）
    assignments = []  # (job_row, [candidate_rows])
    used_ids = set()
    for jr in job_rows:
        req_text = pick(jr, job_fields, "岗位要求")
        pos_level = pick(jr, job_fields, "级别")
        pos_terms = match_terms(req_text)
        remaining = [r for r in pool if id(r) not in used_ids]
        ranked = sorted(
            remaining,
            key=lambda r: position_sort_key(r, resume_fields, pos_terms, pos_level),
        )
        picks = ranked[:TOPN]
        assignments.append((jr, picks))
        for r in picks:
            used_ids.add(id(r))

    # 5. 输出：主表（岗位维度 Top5，互不重复）
    print("### 海尔招聘中含JAVA岗位 × 简历库匹配Top5（技术栈匹配优先，岗位间不重复）\n")
    header = ["岗位", "需求团队", "级别·人数", "人天单价", "匹配度最高5人（排名1-5）"]
    rows_out = []
    for jr, picks in assignments:
        pos = str(pick(jr, job_fields, "岗位")).strip()
        team = str(pick(jr, job_fields, "需求团队") or "").strip()
        level = str(pick(jr, job_fields, "级别") or "").strip()
        num = str(pick(jr, job_fields, "需求人数") or "").strip()
        price = str(pick(jr, job_fields, "人天单价") or "").strip()
        top5 = "; ".join(fmt_candidate(r, resume_fields) for r in picks)
        rows_out.append([pos, team, "%s·%s人" % (level, num), price, top5])

    widths = [max(len(str(r[i])) for r in rows_out + [header]) for i in range(len(header))]
    print("| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(header)) + " |")
    print("| " + " | ".join("-" * w for w in widths) + " |")
    for r in rows_out:
        print("| " + " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(r)) + " |")

    # 6. 匹配依据明细表（逐岗位逐人，含命中技术词）
    print("\n### 匹配依据明细（命中技术词 = 岗位要求关键词 ∩ 候选人技术评价）\n")
    d_header = ["岗位", "名次", "姓名", "评级", "期望薪资", "面试时间", "得分", "命中技术词", "技术评价要点"]
    d_rows = []
    for jr, picks in assignments:
        pos = str(pick(jr, job_fields, "岗位")).strip()
        team = str(pick(jr, job_fields, "需求团队") or "").strip()
        req_text = pick(jr, job_fields, "岗位要求")
        pos_level = pick(jr, job_fields, "级别")
        pos_terms = match_terms(req_text)
        pos_label = "%s·%s" % (team, pos)
        for i, r in enumerate(picks, 1):
            cand_text = str(pick(r, resume_fields, "技术评价") or "").strip()
            hits = sorted(match_terms(cand_text) & pos_terms)
            tech = cand_text.replace("\n", " ")
            d_rows.append([
                pos_label,
                i,
                str(pick(r, resume_fields, "候选人姓名")).strip(),
                str(pick(r, resume_fields, "面试评级") or "").strip() or "空",
                str(pick(r, resume_fields, "期望薪资") or "").strip() or "未填",
                str(pick(r, resume_fields, "面试时间") or "").strip()[:10],
                fit_score(cand_text, pos_terms, pos_level),
                "、".join(hits[:8]),
                tech[:60],
            ])
    dw = [max(len(str(x[i])) for x in d_rows + [d_header]) for i in range(len(d_header))]
    print("| " + " | ".join(h.ljust(dw[i]) for i, h in enumerate(d_header)) + " |")
    print("| " + " | ".join("-" * w for w in dw) + " |")
    for d in d_rows:
        print("| " + " | ".join(str(c).ljust(dw[i]) for i, c in enumerate(d)) + " |")

    # 7. 去重校验
    all_names = []
    for jr, picks in assignments:
        for r in picks:
            all_names.append(str(pick(r, resume_fields, "候选人姓名")).strip())
    dup = len(all_names) - len(set(all_names))
    print("\n去重校验：共 %d 个名额，重复 %d 个，候选池 %d 人。" % (len(all_names), dup, len(pool)))


if __name__ == "__main__":
    main()
