import json
import sqlite3
import pandas as pd
from config import DB, DATA, YEARS, CATEGORIES, TYPES, PLATFORMS

def filter_clause(year=None, platform=None, category=None, issue_type=None):
    clauses, params = [], []
    for col, val in [("platform",platform),("category",category),("issue_type",issue_type)]:
        if val:
            clauses.append(f"{col}=?")
            params.append(val)
    if year is not None:
        clauses.append("substr(complaint_date,1,4)=?")
        params.append(str(year))
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), params

def read_filtered(year=None, platform=None, category=None, issue_type=None):
    where, params = filter_clause(year, platform, category, issue_type)
    with sqlite3.connect(DB) as con:
        return pd.read_sql_query("SELECT * FROM complaints" + where, con, params=params)

def read_page(filters, page, page_size):
    where, params = filter_clause(**filters)
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        total = con.execute("SELECT COUNT(*) FROM complaints" + where, params).fetchone()[0]
        items = con.execute(
            "SELECT * FROM complaints" + where +
            " ORDER BY complaint_date DESC, complaint_id DESC, source_id DESC LIMIT ? OFFSET ?",
            [*params, page_size, (page-1)*page_size]).fetchall()
    return dict(total=total, page=page, page_size=page_size, items=[dict(row) for row in items])

def summarize(df, selected_year=None):
    n = len(df)
    years = [selected_year] if selected_year else YEARS
    def distribution(col, universe):
        counts = df[col].value_counts().reindex(universe, fill_value=0)
        return [dict(name=k, count=int(v), share=float(v/n) if n else None)
                for k,v in counts.items()]
    annual_counts = df.complaint_date.str[:4].value_counts()
    annual = [dict(year=y,count=int(annual_counts.get(str(y),0))) for y in years]
    months = [f"{y}-{m:02d}" for y in years for m in range(1,13)]
    monthly_counts = df.complaint_date.str[:7].value_counts()
    monthly = [dict(month=m,count=int(monthly_counts.get(m,0))) for m in months]
    cross = pd.crosstab(df.category,df.issue_type).reindex(
        index=CATEGORIES, columns=TYPES, fill_value=0)
    matrix = []
    for c in CATEGORIES:
        denom = int(cross.loc[c].sum())
        for t in TYPES:
            value = int(cross.loc[c,t])
            matrix.append(dict(category=c,issue_type=t,count=value,
                               row_share=float(value/denom) if denom else None))
    platform_types = []
    for p in PLATFORMS:
        sub = df.loc[df.platform.eq(p)]
        denom = len(sub)
        for t in TYPES:
            count = int(sub.issue_type.eq(t).sum())
            platform_types.append(dict(platform=p,issue_type=t,count=count,
                                       share=float(count/denom) if denom else None))
    type_year = []
    for y in years:
        sub = df.loc[df.complaint_date.str[:4].eq(str(y))]
        for t in TYPES:
            type_year.append(dict(year=y,issue_type=t,count=int(sub.issue_type.eq(t).sum())))
    closed = df.loc[df.status.eq("已办结")]
    duration = (pd.to_datetime(closed.resolved_date)-pd.to_datetime(closed.complaint_date)).dt.days
    return dict(total=n,closed_count=len(closed),closure_share=len(closed)/n if n else None,
                median_amount=float(df.amount.median()) if n else None,
                closed_duration_median=float(duration.median()) if len(closed) else None,
                annual=annual,monthly=monthly,types=distribution("issue_type",TYPES),
                categories=distribution("category",CATEGORIES),matrix=matrix,
                platform_types=platform_types,type_year=type_year)

def metadata():
    return dict(data_kind="simulated", source_id="demo-v1", unit="条",
                note="演示数据；所有图表仅描述当前模拟样本，不代表真实平台或全国情况。",
                coverage={"start":"2023-01-01","end":"2025-12-31","complete":True},
                generation=json.loads((DATA/"generation.json").read_text(encoding="utf-8")),
                quality=json.loads((DATA/"quality.json").read_text(encoding="utf-8")))
