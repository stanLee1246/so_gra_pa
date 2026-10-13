"""生成可复现演示数据；所有生成参数均为工程假设，不代表现实分布。"""
import argparse
import calendar
import json
import numpy as np
import pandas as pd
from config import DATA, YEARS, PLATFORMS, CATEGORIES, TYPES, CUTOFF

def generate(seed=42, per_year=4000, scenario="baseline"):
    if per_year < 20 or seed < 0 or scenario not in {"baseline", "promotion"}:
        raise ValueError("种子须非负、每年至少20条，场景须为baseline或promotion")
    rng = np.random.default_rng(seed)
    rows = []
    # 基线不注入增长、季节性或品类关联；促销场景仅用于软件识别能力实验。
    weights = np.ones(12)
    if scenario == "promotion":
        weights[[6, 11]] = 2  # 人为增加7月、12月；不可作为促销因果证据
    weights = weights / weights.sum()
    for year in YEARS:
        for _ in range(per_year):
            month = int(rng.choice(np.arange(1, 13), p=weights))
            day = int(rng.integers(1, calendar.monthrange(year, month)[1]+1))
            date = pd.Timestamp(year, month, day)
            closed = bool(rng.random() < .75)
            resolved = date + pd.Timedelta(days=int(rng.integers(1, 31)))
            closed = closed and resolved <= pd.Timestamp(CUTOFF)
            rows.append(dict(
                complaint_id=f"DEMO-{len(rows)+1:07d}", complaint_date=date.strftime("%Y-%m-%d"),
                platform=str(rng.choice(PLATFORMS)), category=str(rng.choice(CATEGORIES[:-1])),
                issue_type=str(rng.choice(TYPES)), amount=round(float(rng.lognormal(5, .9)), 2),
                status="已办结" if closed else "处理中",
                resolved_date=resolved.strftime("%Y-%m-%d") if closed else "",
                complainant_role="consumer", record_kind="complaint",
                source_id="demo-v1", data_kind="simulated"))
    clean = pd.DataFrame(rows)
    dirty = clean.head(20).copy()
    extras = clean.head(20).copy()
    extras["complaint_id"] = [f"DIRTY-{i:04d}" for i in range(20)]
    extras.loc[extras.index[:5], "complaint_date"] = "bad-date"
    extras.loc[extras.index[5:10], "amount"] = -100
    extras.loc[extras.index[10:], "category"] = None
    raw = pd.concat([clean, dirty, extras], ignore_index=True)
    DATA.mkdir(parents=True, exist_ok=True)
    raw.to_csv(DATA/"raw_demo.csv", index=False, encoding="utf-8-sig")
    meta = dict(seed=seed, per_year=per_year, scenario=scenario, cutoff=CUTOFF,
                original_rows=len(clean), raw_rows=len(raw), data_kind="simulated",
                assumptions="年份等样本量；平台、品类、类型独立抽样；金额及办结情况人为生成")
    (DATA/"generation.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--per-year", type=int, default=4000)
    p.add_argument("--scenario", choices=["baseline", "promotion"], default="baseline")
    a = p.parse_args()
    if a.per_year < 20:
        p.error("--per-year 必须至少为20")
    generate(a.seed, a.per_year, a.scenario)
