import io
import time
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from config import BASE, DB, YEARS, PLATFORMS, CATEGORIES, TYPES
from analysis import read_filtered, read_page, summarize, metadata

app = FastAPI(title="网购投诉特征分析：演示版")
app.mount("/static", StaticFiles(directory=BASE/"static"), name="static")

def filters(year: Optional[int]=Query(None,ge=2023,le=2025),
            platform: Optional[str]=None,category: Optional[str]=None,
            issue_type: Optional[str]=None):
    if not DB.exists():
        raise HTTPException(503,"请先生成并预处理数据")
    for value, allowed in [(platform,PLATFORMS),(category,CATEGORIES),(issue_type,TYPES)]:
        if value is not None and value not in allowed:
            raise HTTPException(422,"筛选值不在字典中")
    return dict(year=year,platform=platform,category=category,issue_type=issue_type)

@app.get("/")
def index():
    return FileResponse(BASE/"static"/"index.html")

@app.get("/api/meta")
def meta():
    if not DB.exists():
        raise HTTPException(503,"请先生成并预处理数据")
    return dict(**metadata(),years=YEARS,platforms=PLATFORMS,categories=CATEGORIES,types=TYPES)

@app.get("/api/dashboard")
def dashboard(f=Depends(filters)):
    start = time.perf_counter()
    result = summarize(read_filtered(**f),f["year"])
    return dict(meta=metadata(),filters=f,metrics=result,
                elapsed_ms=round((time.perf_counter()-start)*1000,2))

@app.get("/api/records")
def records(page:int=Query(1,ge=1),page_size:int=Query(10,ge=1,le=100),f=Depends(filters)):
    return read_page(f, page, page_size)

@app.get("/api/export")
def export(f=Depends(filters)):
    df = read_filtered(**f)
    # 对未来外部数据的文本单元格做公式转义；演示数据中也保留此步骤。
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].map(lambda x: "'"+x if isinstance(x,str) and
                             x.lstrip().startswith(("=","+","-","@")) else x)
    raw = df.to_csv(index=False).encode("utf-8-sig")
    return StreamingResponse(io.BytesIO(raw),media_type="text/csv",
        headers={"Content-Disposition":'attachment; filename="simulated_complaints.csv"'})
