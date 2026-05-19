#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///

import requests, base64, os, sys

url = "http://216.132.133.113:3005/v1/images/generations"
headers = {
    "Authorization": "Bearer sk-eC5mIXG4OUzQlW8ACcji9NxVAa9hc2o7",
    "Content-Type": "application/json"
}

prompt = """A clean technical architecture diagram showing how an AI search proxy skill works.
Landscape 16:9 widescreen format. Dark background #0d1117. Blue accents #58a6ff. White text.

The diagram shows a horizontal data flow with labeled boxes and arrows:

LEFT: Robot icon box labeled "Claude AI" with speech bubble "搜索最新消息?"

ARROW pointing right →

CENTER-LEFT: Rounded rectangle box labeled "easy_anysearch_skill\nsearch.py" with a small Python snake icon

ARROW pointing right →

CENTER: Box labeled "Proxy Pool 代理池" containing a cluster of small server nodes with IP addresses like "45.x.x.x:1080", "103.x.x.x:8080" etc. A lightning bolt icon ⚡ above labeled "并发探测" (concurrent probe). One node highlighted in green with checkmark ✓ labeled "最快可用"

ARROW pointing right →

CENTER-RIGHT: Server icon box labeled "AnySearch API\napi.anysearch.com" with a magnifying glass icon

ARROW pointing left ←  (return path, dashed line)

The return arrow brings back: JSON results bubble showing {"results": [...]}

Style: Flat design, monospace code font for labels, subtle connecting lines, professional technical documentation aesthetic. No decorative art, pure information design."""

print("正在生成图片...", flush=True)
resp = requests.post(url, headers=headers, json={
    "model": "gpt-image-2",
    "prompt": prompt,
    "n": 1,
    "size": "1536x1024",
    "response_format": "b64_json",
    "quality": "high"
}, timeout=180)

data = resp.json()
if "data" in data:
    img_b64 = data["data"][0]["b64_json"]
    out = os.path.join(os.path.dirname(__file__), "architecture.png")
    with open(out, "wb") as f:
        f.write(base64.b64decode(img_b64))
    print(f"生成成功: {out}")
else:
    print("ERROR:", data, file=sys.stderr)
    sys.exit(1)
