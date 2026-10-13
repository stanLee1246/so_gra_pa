"""检查统计口径、SQL/Pandas一致性、筛选、导出及空样本；无需启动服务。"""
import io
import sqlite3
import pandas as pd
from fastapi.testclient import TestClient
from app import app
from config import DB, DATA
from analysis import summarize

def main():
    c = TestClient(app)
    r = c.get("/api/dashboard")
    assert r.status_code == 200
    payload = r.json()
    m = payload["metrics"]
    n = m["total"]
    with sqlite3.connect(DB) as con:
        assert con.execute("SELECT COUNT(*) FROM complaints").fetchone()[0] == n
        sql = dict(con.execute("SELECT issue_type,COUNT(*) FROM complaints GROUP BY issue_type"))
    assert {d["name"]:d["count"] for d in m["types"]} == sql
    for key in ["annual","monthly","types","categories"]:
        assert sum(d["count"] for d in m[key]) == n
    assert sum(d["count"] for d in m["matrix"]) == n
    assert abs(sum(d["share"] for d in m["types"])-1) < 1e-12
    q = payload["meta"]["quality"]
    assert q["raw_rows"]==q["rejected_rows"]+q["duplicate_rows"]+q["clean_rows"]
    assert q["duplicate_rows"]==20 and q["rejected_rows"]==10
    assert len(m["monthly"])==36
    path = "/api/dashboard?year=2024&platform=演示平台A&category=食品"
    sub = c.get(path).json()["metrics"]["total"]
    with sqlite3.connect(DB) as con:
        expected = con.execute("SELECT COUNT(*) FROM complaints WHERE substr(complaint_date,1,4)=? AND platform=? AND category=?",("2024","演示平台A","食品")).fetchone()[0]
    assert sub==expected
    export = c.get("/api/export?year=2024&platform=演示平台A&category=食品")
    assert len(pd.read_csv(io.BytesIO(export.content)))==expected
    assert c.get("/api/dashboard?year=2022").status_code==422
    assert c.get("/api/dashboard?platform=不存在").status_code==422
    assert c.get("/api/records?page=0").status_code==422
    assert c.get("/api/records?page=99999").json()["items"]==[]
    empty = pd.read_csv(DATA/"clean_demo.csv").head(0)
    assert summarize(empty)["total"]==0
    assert summarize(empty)["median_amount"] is None
    assert c.get("/").status_code==200
    assert c.get("/static/vendor/echarts.min.js").status_code==200
    print(f"验证通过：{n}条，统计守恒；SQL/Pandas一致；筛选/CSV/分页/空样本通过。")

if __name__ == "__main__":
    main()
