"""CSV -> 校验/隔离 -> 去重 -> SQLite；数据库仅保存本次演示快照。"""
import json
import sqlite3
import hashlib
import numpy as np
import pandas as pd
from config import DATA, DB, YEARS, PLATFORMS, CATEGORIES, TYPES, CUTOFF

def prepare():
    path = DATA/"raw_demo.csv"
    df = pd.read_csv(path)
    required = ["complaint_id","complaint_date","platform","category","issue_type",
                "amount","status","resolved_date","complainant_role","record_kind",
                "source_id","data_kind"]
    missing = set(required)-set(df.columns)
    if missing:
        raise ValueError(f"缺少字段：{missing}")
    for col in ["complaint_id","platform","category","issue_type","source_id"]:
        df[col] = df[col].astype("string").str.strip()
    df["category"] = df["category"].fillna("未知").replace("", "未知")
    dates = pd.to_datetime(df["complaint_date"], format="%Y-%m-%d", errors="coerce")
    resolved = pd.to_datetime(df["resolved_date"], format="%Y-%m-%d", errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    bad = (df["complaint_id"].isna() | df["complaint_id"].eq("").fillna(True) |
           dates.isna() | ~dates.dt.year.isin(YEARS) |
           ~df["platform"].isin(PLATFORMS) | ~df["category"].isin(CATEGORIES) |
           ~df["issue_type"].isin(TYPES) | ~df["status"].isin(["已办结","处理中"]) |
           ~df["complainant_role"].eq("consumer") | ~df["record_kind"].eq("complaint") |
           ~df["source_id"].eq("demo-v1") | ~df["data_kind"].eq("simulated") |
           ~np.isfinite(df["amount"]) | df["amount"].lt(0) |
           (df["status"].eq("已办结") &
            (resolved.isna() | resolved.lt(dates) | resolved.gt(pd.Timestamp(CUTOFF)))) |
           (df["status"].eq("处理中") & df["resolved_date"].notna()))
    valid = df.loc[~bad].copy()
    key = ["source_id","complaint_id"]
    duplicate = valid.duplicated(key, keep="first")
    # 相同ID不同内容不能静默覆盖；本演示样本仅包含完全重复记录。
    for _, group in valid.loc[valid.duplicated(key, keep=False)].groupby(key):
        if len(group.drop_duplicates()) > 1:
            raise ValueError("同源同ID内容冲突，请人工核验")
    cleaned = valid.loc[~duplicate].copy()
    cleaned["complaint_date"] = dates.loc[cleaned.index].dt.strftime("%Y-%m-%d")
    cleaned["resolved_date"] = resolved.loc[cleaned.index].dt.strftime("%Y-%m-%d").fillna("")
    df.loc[bad].assign(reject_reason="字段或范围校验失败").to_csv(
        DATA/"rejected.csv", index=False, encoding="utf-8-sig")
    cleaned.to_csv(DATA/"clean_demo.csv", index=False, encoding="utf-8-sig")
    with sqlite3.connect(DB) as con:
        con.execute("PRAGMA foreign_keys=ON")
        con.executescript("""
            DROP VIEW IF EXISTS ads_monthly;
            DROP TABLE IF EXISTS complaints;
            DROP TABLE IF EXISTS sources;
            CREATE TABLE sources(
                source_id TEXT PRIMARY KEY NOT NULL, data_kind TEXT NOT NULL,
                scope TEXT NOT NULL, observation_cutoff TEXT NOT NULL);
            INSERT INTO sources VALUES('demo-v1','simulated','consumer physical-goods complaints','2025-12-31');
            CREATE TABLE complaints(
                complaint_id TEXT NOT NULL, complaint_date TEXT NOT NULL,
                platform TEXT NOT NULL, category TEXT NOT NULL, issue_type TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount>=0),
                status TEXT NOT NULL CHECK(status IN ('已办结','处理中')), resolved_date TEXT,
                complainant_role TEXT NOT NULL CHECK(complainant_role='consumer'),
                record_kind TEXT NOT NULL CHECK(record_kind='complaint'),
                source_id TEXT NOT NULL REFERENCES sources(source_id),
                data_kind TEXT NOT NULL CHECK(data_kind='simulated'),
                PRIMARY KEY(source_id,complaint_id));
        """)
        cols = required
        con.executemany(
            "INSERT INTO complaints("+",".join(cols)+") VALUES("+",".join(["?"]*len(cols))+")",
            cleaned[cols].itertuples(index=False, name=None))
        con.executescript("""
            CREATE INDEX idx_date ON complaints(complaint_date);
            CREATE INDEX idx_platform_category ON complaints(platform,category);
            CREATE VIEW ads_monthly AS
                SELECT substr(complaint_date,1,7) AS month, platform, category, issue_type,
                       COUNT(*) AS complaint_count
                FROM complaints GROUP BY month,platform,category,issue_type;
        """)
    report = dict(raw_rows=len(df), rejected_rows=int(bad.sum()),
                  duplicate_rows=int(duplicate.sum()), clean_rows=len(cleaned),
                  unknown_category_rows=int(cleaned.category.eq("未知").sum()),
                  raw_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  conservation_ok=len(df)==int(bad.sum())+int(duplicate.sum())+len(cleaned))
    (DATA/"quality.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return report

if __name__ == "__main__":
    prepare()
