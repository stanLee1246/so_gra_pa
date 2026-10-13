from pathlib import Path
import os
BASE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("COMPLAINT_DATA_DIR", BASE / "data")).resolve()
DB = DATA / "complaints.db"
YEARS = [2023, 2024, 2025]
PLATFORMS = ["演示平台A", "演示平台B", "演示平台C"]
CATEGORIES = ["服装鞋帽", "家用电器", "食品", "数码产品", "日用品", "美妆护肤", "未知"]
TYPES = ["退款退货", "商品质量", "物流配送", "售后响应", "宣传不符",
         "价格争议", "订单履约", "支付争议", "个人信息", "其他"]
CUTOFF = "2025-12-31"
