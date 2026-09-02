# Codex Interviewer Skills

面向招聘面试场景的 Codex 技能集，包含五个技能：

| 技能 | 说明 |
|---|---|
| `java-interviewer` | 资深 Java 面试官出题工作流：读简历 + 固定 JD → 生成《面试题与评分表》合一文档（候选人核验信息、JD 匹配检查、简历分析、6 道定制题、参考答案、回答记录区） |
| `java-evaluator` | Java 面试评估：读取已填写回答记录的评分表 → 生成《候选人评估报告》（建议等级 + A/B/C/D 面试评级、五维评估、录用建议、二面重点清单） |
| `test-interviewer` | 测试工程师简历筛选与核验建档：按固定 JD 判断符合性 → 创建候选人文件夹、保存简历、生成《候选人核验信息表》 |
| `fe-interviewer` | 资深前端面试官出题工作流（业务前端 + Vue 3 岗，专为电话面试设计）：读简历 + 固定 JD → 生成《面试题与评分表》合一文档（候选人核验信息、固定 6 题口述题、参考答案、回答记录区）；毕业不足 4 年直接拒绝留档 |
| `fe-evaluator` | 前端面试评估：读取已填写回答记录的评分表 → 生成《候选人评估报告》（建议等级 + A/B/C/D 面试评级、五维评估、录用建议、二面重点清单） |

## 目录结构

```text
skills/
  java-interviewer/    SKILL.md + assets + references + agents
  java-evaluator/      SKILL.md + assets + agents
  test-interviewer/    SKILL.md + assets + agents
  fe-interviewer/      SKILL.md + assets + references + agents
  fe-evaluator/        SKILL.md + assets + agents
```

每个技能目录均以 `SKILL.md` 为入口，符合 Codex 技能规范，可单独安装。

## 在其他 Codex 环境安装

使用 Codex 自带的 skill-installer 脚本安装（一次性装全部五个）：

```bash
python3 <skill-installer>/scripts/install-skill-from-github.py \
  --repo blydd/codex-skills \
  --path skills/java-interviewer skills/java-evaluator skills/test-interviewer skills/fe-interviewer skills/fe-evaluator
```

其中 `<skill-installer>` 为本机 `~/.codex/skills/.system/skill-installer`（也可在任意 Codex 会话中让 Agent 调用该技能代为执行）。

或指定 GitHub 网页地址逐个安装：

```bash
python3 <skill-installer>/scripts/install-skill-from-github.py \
  --url https://github.com/blydd/codex-skills/tree/main/skills/java-interviewer
```

安装后技能会进入 `~/.codex/skills/<技能名>/`，新会话即可使用（技能名为目录 basename：`java-interviewer`、`java-evaluator`、`test-interviewer`、`fe-interviewer`、`fe-evaluator`）。

## 私有仓库

仓库若改为私有，安装方需提供 GitHub 凭证（本机已登录的 git 凭证或 `GH_TOKEN`/`GITHUB_TOKEN` 环境变量），脚本会自动回退到 git sparse checkout。

## 说明

- 技能内容与本地 `~/.codex/skills/` 下的工作版本保持一致，更新技能后重新 push 即可同步。
- 五个技能为配套工作流：`java-interviewer` → `java-evaluator`、`fe-interviewer` → `fe-evaluator`（出题 → 面试填写 → 出评估报告）；`test-interviewer` 独立用于测试岗建档。
