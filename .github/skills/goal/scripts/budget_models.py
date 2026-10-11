#!/usr/bin/env python3
"""Published price/cap snapshot and reproducible planning estimates. No credentials."""
from __future__ import annotations
import json
import math
import re

SOURCE = "https://docs.opencode.ai/docs/go/"
CHECKED = "2026-10-11"
WINDOWS = {"rolling": .2, "weekly": .5, "monthly": 1.0}
# Input, cached read, output, cache-write tokens: a common comparison workload,
# not OpenCode's model-specific request estimates or a promised quota.
PROFILE = (8000, 60000, 2000, 0)
CATALOG = json.loads(r'''{
  "GLM-5.3-Flash": {
    "name": "GLM-5.3-Flash",
    "caps": {
      "go": 60,
      "go-plus": 180
    },
    "rates": {
      "standard": [
        0.15,
        0.5,
        0.03,
        null
      ]
    },
    "quality": [
      4,
      3
    ],
    "family": "glm",
    "excluded": false,
    "training": false
  },
  "GLM-5.3": {
    "name": "GLM-5.3",
    "caps": {
      "go": 15,
      "go-plus": 120
    },
    "rates": {
      "standard": [
        1.4,
        4.4,
        0.26,
        null
      ]
    },
    "quality": [
      5,
      4
    ],
    "family": "glm",
    "excluded": false,
    "training": false
  },
  "GLM-5.2": {
    "name": "GLM-5.2",
    "caps": {
      "go": 60,
      "go-plus": 180
    },
    "rates": {
      "standard": [
        1.4,
        4.4,
        0.26,
        null
      ]
    },
    "quality": [
      5,
      4
    ],
    "family": "glm",
    "excluded": false,
    "training": false
  },
  "Kimi K3": {
    "name": "Kimi K3",
    "caps": {
      "go": 15,
      "go-plus": 60
    },
    "rates": {
      "standard": [
        3,
        15,
        0.3,
        null
      ]
    },
    "quality": [
      5,
      5
    ],
    "family": "kimi",
    "excluded": false,
    "training": false
  },
  "Kimi K2.7 Code": {
    "name": "Kimi K2.7 Code",
    "caps": {
      "go": 60,
      "go-plus": 180
    },
    "rates": {
      "standard": [
        0.95,
        4,
        0.19,
        null
      ]
    },
    "quality": [
      3,
      3
    ],
    "family": "kimi",
    "excluded": true,
    "training": false
  },
  "Kimi K2.6": {
    "name": "Kimi K2.6",
    "caps": {
      "go": 60,
      "go-plus": 240
    },
    "rates": {
      "standard": [
        0.95,
        4,
        0.16,
        null
      ]
    },
    "quality": [
      3,
      3
    ],
    "family": "kimi",
    "excluded": true,
    "training": false
  },
  "LongCat-2.0": {
    "name": "LongCat-2.0",
    "caps": {
      "go": 60,
      "go-plus": 240
    },
    "rates": {
      "standard": [
        0.3,
        1.2,
        0.006,
        null
      ]
    },
    "quality": [
      2,
      2
    ],
    "family": "longcat",
    "excluded": false,
    "training": false
  },
  "LongCat 2.5 Preview Free": {
    "name": "LongCat 2.5 Preview Free",
    "caps": {
      "go": null,
      "go-plus": null
    },
    "rates": {
      "standard": [
        0,
        0,
        0,
        null
      ]
    },
    "quality": [
      2,
      2
    ],
    "family": "longcat",
    "excluded": false,
    "training": false
  },
  "Step 5 Preview Free": {
    "name": "Step 5 Preview Free",
    "caps": {
      "go": null,
      "go-plus": null
    },
    "rates": {
      "standard": [
        0,
        0,
        0,
        null
      ]
    },
    "quality": [
      2,
      2
    ],
    "family": "step",
    "excluded": false,
    "training": false
  },
  "MiMo-V2.6-Flash": {
    "name": "MiMo-V2.6-Flash",
    "caps": {
      "go": 60,
      "go-plus": 120
    },
    "rates": {
      "standard": [
        0.14,
        0.28,
        0.0028,
        null
      ]
    },
    "quality": [
      3,
      3
    ],
    "family": "mimo",
    "excluded": false,
    "training": false
  },
  "MiMo-V2.6-Pro": {
    "name": "MiMo-V2.6-Pro",
    "caps": {
      "go": 15,
      "go-plus": 60
    },
    "rates": {
      "standard": [
        0.435,
        0.87,
        0.003625,
        null
      ]
    },
    "quality": [
      4,
      4
    ],
    "family": "mimo",
    "excluded": false,
    "training": false
  },
  "MiMo-V2.5": {
    "name": "MiMo-V2.5",
    "caps": {
      "go": 60,
      "go-plus": 120
    },
    "rates": {
      "standard": [
        0.14,
        0.28,
        0.0028,
        null
      ]
    },
    "quality": [
      3,
      3
    ],
    "family": "mimo",
    "excluded": false,
    "training": false
  },
  "MiMo-V2.5-Pro": {
    "name": "MiMo-V2.5-Pro",
    "caps": {
      "go": 15,
      "go-plus": 60
    },
    "rates": {
      "standard": [
        0.435,
        0.87,
        0.003625,
        null
      ]
    },
    "quality": [
      4,
      3
    ],
    "family": "mimo",
    "excluded": false,
    "training": false
  },
  "MiniMax M3": {
    "name": "MiniMax M3",
    "caps": {
      "go": 60,
      "go-plus": 180
    },
    "rates": {
      "standard": [
        0.3,
        1.2,
        0.06,
        null
      ]
    },
    "quality": [
      3,
      3
    ],
    "family": "minimax",
    "excluded": false,
    "training": false
  },
  "MiniMax M2.7": {
    "name": "MiniMax M2.7",
    "caps": {
      "go": 60,
      "go-plus": 240
    },
    "rates": {
      "standard": [
        0.3,
        1.2,
        0.06,
        0.375
      ]
    },
    "quality": [
      3,
      3
    ],
    "family": "minimax",
    "excluded": false,
    "training": false
  },
  "Muse Spark 1.3 Contributor": {
    "name": "Muse Spark 1.3 Contributor",
    "caps": {
      "go": 60,
      "go-plus": 120
    },
    "rates": {
      "standard": [
        0.1,
        0.2,
        0.002,
        null
      ]
    },
    "quality": [
      3,
      3
    ],
    "family": "muse",
    "excluded": false,
    "training": true
  },
  "Muse Spark 1.2 Contributor": {
    "name": "Muse Spark 1.2 Contributor",
    "caps": {
      "go": 60,
      "go-plus": 120
    },
    "rates": {
      "standard": [
        0.1,
        0.2,
        0.002,
        null
      ]
    },
    "quality": [
      3,
      3
    ],
    "family": "muse",
    "excluded": false,
    "training": true
  },
  "Qwen3.8 Max": {
    "name": "Qwen3.8 Max",
    "caps": {
      "go": 15,
      "go-plus": 60
    },
    "rates": {
      "standard": [
        2,
        6,
        0.25,
        2.5
      ]
    },
    "quality": [
      5,
      5
    ],
    "family": "qwen3.8",
    "excluded": false,
    "training": false
  },
  "Qwen3.8 Flash": {
    "name": "Qwen3.8 Flash",
    "caps": {
      "go": 30,
      "go-plus": 90
    },
    "rates": {
      "standard": [
        0.15,
        0.47,
        0.016,
        0.2
      ]
    },
    "quality": [
      3,
      3
    ],
    "family": "qwen3.8",
    "excluded": false,
    "training": false
  },
  "Qwen3.7 Plus": {
    "name": "Qwen3.7 Plus",
    "caps": {
      "go": 60,
      "go-plus": 180
    },
    "rates": {
      "(≤ 256K tokens)": [
        0.4,
        1.6,
        0.04,
        0.5
      ],
      "(> 256K tokens)": [
        1.2,
        4.8,
        0.12,
        1.5
      ]
    },
    "quality": [
      4,
      3
    ],
    "family": "qwen3.7",
    "excluded": false,
    "training": false
  },
  "DeepSeek V4.1 Flash": {
    "name": "DeepSeek V4.1 Flash",
    "caps": {
      "go": 60,
      "go-plus": 120
    },
    "rates": {
      "(Off-Peak)": [
        0.15,
        0.6,
        0.003,
        null
      ],
      "(Peak)": [
        0.3,
        1.2,
        0.006,
        null
      ]
    },
    "quality": [
      3,
      3
    ],
    "family": "deepseek",
    "excluded": false,
    "training": false
  },
  "DeepSeek V4 Pro": {
    "name": "DeepSeek V4 Pro",
    "caps": {
      "go": 15,
      "go-plus": 60
    },
    "rates": {
      "(Off-Peak)": [
        0.66,
        1.98,
        0.022,
        null
      ],
      "(Peak)": [
        1.32,
        3.96,
        0.044,
        null
      ]
    },
    "quality": [
      5,
      5
    ],
    "family": "deepseek",
    "excluded": false,
    "training": false
  },
  "DeepSeek V4 Flash": {
    "name": "DeepSeek V4 Flash",
    "caps": {
      "go": 30,
      "go-plus": 120
    },
    "rates": {
      "(Off-Peak)": [
        0.15,
        0.6,
        0.003,
        null
      ],
      "(Peak)": [
        0.3,
        1.2,
        0.006,
        null
      ]
    },
    "quality": [
      3,
      3
    ],
    "family": "deepseek",
    "excluded": false,
    "training": false
  },
  "DeepSeek V4 Flash Vision Exp": {
    "name": "DeepSeek V4 Flash Vision Exp",
    "caps": {
      "go": 15,
      "go-plus": 60
    },
    "rates": {
      "(Off-Peak)": [
        0.15,
        0.6,
        0.003,
        null
      ],
      "(Peak)": [
        0.3,
        1.2,
        0.006,
        null
      ]
    },
    "quality": [
      3,
      3
    ],
    "family": "deepseek",
    "excluded": false,
    "training": false
  },
  "Hy4 preview": {
    "name": "Hy4 preview",
    "caps": {
      "go": 30,
      "go-plus": 120
    },
    "rates": {
      "standard": [
        0.834,
        2.501,
        0.042,
        null
      ]
    },
    "quality": [
      4,
      5
    ],
    "family": "hy4",
    "excluded": false,
    "training": false
  },
  "Hy3": {
    "name": "Hy3",
    "caps": {
      "go": 60,
      "go-plus": 240
    },
    "rates": {
      "standard": [
        0.14,
        0.58,
        0.035,
        null
      ]
    },
    "quality": [
      3,
      3
    ],
    "family": "hy3",
    "excluded": false,
    "training": false
  },
  "Space Bunny": {
    "name": "Space Bunny",
    "caps": {
      "go": 30,
      "go-plus": 120
    },
    "rates": {
      "standard": [
        0.15,
        0.6,
        0.03,
        null
      ]
    },
    "quality": [
      2,
      2
    ],
    "family": "space",
    "excluded": false,
    "training": false
  },
  "Grok 4.7": {
    "name": "Grok 4.7",
    "caps": {
      "go": 15,
      "go-plus": 60
    },
    "rates": {
      "(≤ 200K tokens)": [
        2,
        6,
        0.5,
        null
      ],
      "(> 200K tokens)": [
        4,
        12,
        1,
        null
      ]
    },
    "quality": [
      3,
      3
    ],
    "family": "grok",
    "excluded": false,
    "training": false
  },
  "Grok 4.6": {
    "name": "Grok 4.6",
    "caps": {
      "go": 15,
      "go-plus": 60
    },
    "rates": {
      "(≤ 200K tokens)": [
        2,
        6,
        0.5,
        null
      ],
      "(> 200K tokens)": [
        4,
        12,
        1,
        null
      ]
    },
    "quality": [
      3,
      3
    ],
    "family": "grok",
    "excluded": false,
    "training": false
  },
  "GPT 6 Luna": {
    "name": "GPT 6 Luna",
    "caps": {
      "go": 15,
      "go-plus": 60
    },
    "rates": {
      "(≤ 272K tokens)": [
        0.1,
        0.5,
        0.01,
        0.125
      ],
      "(> 272K tokens)": [
        0.2,
        0.75,
        0.02,
        0.25
      ]
    },
    "quality": [
      4,
      4
    ],
    "family": "openai",
    "excluded": false,
    "training": false
  },
  "GPT 5.6 Luna": {
    "name": "GPT 5.6 Luna",
    "caps": {
      "go": 15,
      "go-plus": 60
    },
    "rates": {
      "(≤ 272K tokens)": [
        0.2,
        1.2,
        0.02,
        0.25
      ],
      "(> 272K tokens)": [
        0.4,
        1.8,
        0.04,
        0.5
      ]
    },
    "quality": [
      4,
      4
    ],
    "family": "openai",
    "excluded": false,
    "training": false
  },
  "Claude Haiku 5.5": {
    "name": "Claude Haiku 5.5",
    "caps": {
      "go": 15,
      "go-plus": 60
    },
    "rates": {
      "(≤ 100K tokens)": [
        0.1,
        0.5,
        0.01,
        0.125
      ],
      "(> 100K tokens)": [
        0.5,
        2.5,
        0.05,
        0.625
      ]
    },
    "quality": [
      4,
      4
    ],
    "family": "claude",
    "excluded": false,
    "training": false
  }
}''')
EXCLUDED = {"Kimi K2.6", "Kimi K2.7 Code"}

# Authoritative baseline preferences per role. Canonical CATALOG names.
# Quality ratings in CATALOG serve a different purpose and never replace these.
BUILDER_PRECEDENCE = (
    "DeepSeek V4 Pro",
    "GLM-5.3-Flash",
    "GLM-5.2",
    "DeepSeek V4.1 Flash",
    "MiMo-V2.6-Flash",
)

INSPECTOR_PRECEDENCE = (
    "Hy4 preview",
    "GPT 5.6 Luna",
    "Kimi K3",
    "Qwen3.8 Max",
    "Hy3",
)

PREMIUM_BUILDER_MODELS = (
    "GLM-5.3",
)

OPENROUTER_BUILDER_PRECEDENCE = (
    "GLM-5.3-Flash",
)

OPENROUTER_INSPECTOR_PRECEDENCE = (
    "GLM-5.3-Flash",
    "DeepSeek V4.1 Flash",
)


def canonical(label: str) -> str:
    text = label.lower().replace("(new)", "")
    text = re.sub(r"\((?:go|opencode|opencodego|openrouter)\)", "", text)
    text = re.sub(r"^(?:opencode-go/|opencode/|openrouter/|z.ai:|deepseek:)", "", text)
    key = re.sub(r"[^a-z0-9]", "", text)
    for name in CATALOG:
        if re.sub(r"[^a-z0-9]", "", name.lower()) == key:
            return name
    return label.strip()


def provider(label: str) -> str:
    if "openrouter" in label.lower():
        return "openrouter"
    name = canonical(label)
    if name in CATALOG and CATALOG[name]["caps"]["go"] is None:
        return "free"
    return "go" if name in CATALOG else "unknown"


def prices(name: str, context: int, off_peak: bool = False) -> list:
    rates = CATALOG[canonical(name)]["rates"]
    if "(Peak)" in rates:
        return rates["(Off-Peak)" if off_peak else "(Peak)"]
    for variant, rate in rates.items():
        match = re.search(r"≤ (\d+)K", variant)
        if match:
            threshold = int(match[1]) * 1000
            return rate if context <= threshold else next(v for k,v in rates.items() if k.startswith("(>"))
    return next(iter(rates.values()))


def estimate(name: str, plan: str, profile=PROFILE, off_peak=False) -> dict:
    name = canonical(name)
    if plan not in ("go", "go-plus"):
        raise ValueError("plan must be go or go-plus")
    if len(profile) != 4 or any(not math.isfinite(x) or x < 0 for x in profile) or sum(profile) <= 0:
        raise ValueError("profile must contain four nonnegative token counts with a positive total")
    rate = prices(name, sum(profile), off_peak)
    # Rates published as input/output/read/write. Profile uses input/read/output/write.
    i, c, o, w = profile
    # When a separate cache-write price is absent, budget those tokens as input.
    cost = (i*rate[0] + c*rate[2] + o*rate[1] + w*(rate[3] if rate[3] is not None else rate[0])) / 1e6
    cap = CATALOG[name]["caps"][plan]
    return {"model": name, "plan": plan, "cost_usd": cost,
            "windows": {key: {"usd": None if cap is None else cap*fraction,
                "requests": None if not cost or cap is None else math.floor(cap*fraction/cost),
                "tokens": None if not cost or cap is None else math.floor(cap*fraction/cost)*sum(profile)}
                for key,fraction in WINDOWS.items()}}


def markdown() -> str:
    lines = ["# OpenCode Go and Go Plus reference", "",
        "Snapshot: " + CHECKED + ". Published prices and caps: [OpenCode Go](" + SOURCE + ").",
        "Generated from scripts/budget_models.py; use opencode_usage.py --catalog --markdown to reproduce the tables.",
        "", "## Allowances and subjective quality", "",
        "Caps are USD-equivalent single-model allowances, not separate wallets. 5h/week/month = 20%/50%/100% of the monthly cap.",
        "Quality B/I is a subjective, provisional coding/Builder and Inspector tier (5 highest); ties are intentional, not benchmark results.",
        "Excluded Kimi models remain here only for completeness; selection and dispatch reject them.",
        "", "| Model | Go 5h/week/month USD | Plus 5h/week/month USD | B/I | Constraints |",
        "|---|---:|---:|:---:|---|"]
    for name,m in CATALOG.items():
        caps = [" / ".join(f"{m['caps'][p]*f:g}" for f in WINDOWS.values()) if m["caps"][p] is not None else "temporary free" for p in ("go","go-plus")]
        note = "EXCLUDED: tool schema" if m["excluded"] else "training use; region restrictions" if m["training"] else "candidate"
        lines.append(f"| {name} | {caps[0]} | {caps[1]} | {m['quality'][0]}/{m['quality'][1]} | {note} |")
    lines += ["", "## Published token prices", "", "USD per million tokens; each pricing regime is shown. '-' means no separate write price published.",
        "", "| Model / regime | Input | Output | Cache read | Cache write |", "|---|---:|---:|---:|---:|"]
    for name,m in CATALOG.items():
        for regime,rate in m["rates"].items():
            lines.append(f"| {name} {regime} | " + " | ".join("-" if v is None else f"{v:g}" for v in rate) + " |")
    lines += ["", "## Calculated estimates, not guaranteed quotas", "",
        "Common comparison request: 8,000 uncached input + 60,000 cached read + 2,000 output tokens; zero cache-write tokens.",
        "Cost = (input×input-price + cached×read-price + output×output-price + writes×write-price)/1,000,000.",
        "Where write price is absent, writes are budgeted at input price. Token totals include billed cache reads; they are not unique content.",
        "Requests = floor(window USD / request cost); tokens = requests × 70,000. Peak prices and the 70K context tier are used below.",
        "These are reproducible scenario estimates, not official request estimates. Cache misses, reasoning/output, tool calls and long context can change them several-fold.",
        "A fresh independent Inspector may have few cache hits: estimate it separately; do not inherit Builder cache assumptions.",
        "", "| Model | Plan | USD/request | Requests 5h/week/month | Million tokens 5h/week/month |",
        "|---|---|---:|---:|---:|"]
    for name in CATALOG:
        for plan in ("go","go-plus"):
            e = estimate(name, plan)
            requests = " / ".join("n/a" if v["requests"] is None else f"{v['requests']:,}" for v in e["windows"].values())
            tokens = " / ".join("n/a" if v["tokens"] is None else f"{v['tokens']/1e6:.2f}" for v in e["windows"].values())
            lines.append(f"| {name} | {plan} | {e['cost_usd']:.6f} | {requests} | {tokens} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(markdown())
