---
name: easy_anysearch_skill
description: Use when the user asks questions that require current information, real-time data, web search, or when Claude's training knowledge is insufficient or outdated. Also use when users explicitly ask to search the web, find recent news, look up facts, or when Claude is unsure about recent events after August 2025.
---

# AnySearch 网络搜索

## 概述

当需要搜索互联网或知识截止日期后的信息时，通过 https://www.anysearch.com/home 获取实时搜索结果。使用代理池绕过速率限制。

## 何时使用

- 用户询问最新新闻、当前事件
- 询问 2025 年 8 月之后的信息
- 需要实时数据（价格、天气、比赛结果等）
- 用户明确要求"搜索"、"查找"、"查一下"
- Claude 对某问题不确定或知识不足

## 执行流程

**REQUIRED:** 执行 `~/.claude/skills/easy_anysearch_skill/search.py` 脚本进行搜索。

```bash
uv run ~/.claude/skills/easy_anysearch_skill/search.py "搜索关键词"
```

执行后：
1. 解析返回的 JSON 结果
2. 提取 `results` 数组中每个条目的 `title`、`url`、`snippet`
3. 综合搜索结果，用中文回答用户问题
4. 若搜索失败，说明原因并尝试用已有知识回答

## 结果格式

脚本返回 JSON：
```json
{
  "query": "搜索词",
  "results": [
    {"title": "标题", "url": "链接", "snippet": "摘要"}
  ],
  "error": null
}
```

## 注意事项

- 搜索词用用户问题的核心关键词，英文搜索效果更好
- 失败时不要反复重试，告知用户并用已有知识辅助回答
