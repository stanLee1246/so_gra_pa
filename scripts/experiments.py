"""保存六组实验与20次API耗时；使用独立目录，保留默认展示数据。"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).resolve().parents[1]
RESULTS = BASE / 'results'


def run():
    RESULTS.mkdir(exist_ok=True)
    reports = []
    for seed in (42, 43, 44):
        for scenario in ('baseline', 'promotion'):
            target = RESULTS / f'{scenario}-{seed}'
            env = {**os.environ, 'COMPLAINT_DATA_DIR': str(target)}
            for script, args in [('generate_demo.py',['--seed',str(seed),'--scenario',scenario]), ('prepare_data.py',[]), ('verify.py',[])]:
                subprocess.run([sys.executable, str(BASE/script), *args], cwd=BASE, env=env, check=True, capture_output=True)
            digest = hashlib.sha256((target/'raw_demo.csv').read_bytes()).hexdigest()
            subprocess.run([sys.executable, str(BASE/'generate_demo.py'), '--seed', str(seed), '--scenario', scenario], cwd=BASE, env=env, check=True, capture_output=True)
            assert hashlib.sha256((target/'raw_demo.csv').read_bytes()).hexdigest() == digest
            code = '''import json, numpy as np
from fastapi.testclient import TestClient
from app import app
client=TestClient(app)
payload=client.get('/api/dashboard').json()
times=[client.get('/api/dashboard').json()['elapsed_ms'] for _ in range(20)]
print(json.dumps({'dashboard':payload,'timing':{'runs':20,'median_ms':float(np.median(times)),'p95_ms':float(np.percentile(times,95)), 'scope':'后端 elapsed_ms，非浏览器完整耗时'}},ensure_ascii=False))
'''
            result = subprocess.run([sys.executable, '-c', code], cwd=BASE, env=env, check=True, capture_output=True, text=True)
            payload = json.loads(result.stdout)
            (target/'dashboard.json').write_text(json.dumps(payload['dashboard'], ensure_ascii=False, indent=2), encoding='utf-8')
            reports.append(dict(seed=seed, scenario=scenario, raw_sha256=digest, repeated_hash_equal=True, verified=True, clean_rows=payload['dashboard']['metrics']['total'], timing=payload['timing']))
            print(f'{scenario}/{seed}: 复现、守恒及接口验证通过')
    (RESULTS/'experiment_summary.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'实验结果保存到 {RESULTS}；默认 data 目录未改动。')


if __name__ == '__main__':
    run()
