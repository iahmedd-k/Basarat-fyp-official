import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "archive"))
from remote_exec import run_remote_python

code = """
import json
from collections import defaultdict
from app.db.base import get_sync_session_factory
from app.models.fundamentals import StockFundamentals

def run_inspection():
    null_counts_by_path = defaultdict(int)
    zero_counts_by_path = defaultdict(int)
    stats = {"total_cells": 0, "total_nulls": 0, "total_zeros": 0, "total_nonzeros": 0, "total_other": 0}

    def inspect_obj(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                p = f"{path}.{k}" if path else k
                inspect_obj(v, p)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                inspect_obj(item, f"{path}[{i}]")
        else:
            stats["total_cells"] += 1
            if obj is None:
                stats["total_nulls"] += 1
                agg_path = ".".join([seg.split("[")[0] for seg in path.split(".")])
                null_counts_by_path[agg_path] += 1
            elif isinstance(obj, (int, float)) and obj == 0:
                stats["total_zeros"] += 1
                agg_path = ".".join([seg.split("[")[0] for seg in path.split(".")])
                zero_counts_by_path[agg_path] += 1
            elif isinstance(obj, (int, float)):
                stats["total_nonzeros"] += 1
            else:
                stats["total_other"] += 1

    with get_sync_session_factory()() as s:
        rows = s.query(StockFundamentals).all()
        print("Total rows:", len(rows))
        for r in rows:
            inspect_obj(r.payload)

    print("Total cells:", stats["total_cells"])
    print("Total nulls:", stats["total_nulls"])
    print("Total zeros:", stats["total_zeros"])
    print("Total nonzeros:", stats["total_nonzeros"])
    print("Total other:", stats["total_other"])
    
    print("\\nTop Null Fields:")
    for p, c in sorted(null_counts_by_path.items(), key=lambda x: x[1], reverse=True)[:35]:
        print(f"  {p}: {c}")
        
    print("\\nTop Zero Fields:")
    for p, c in sorted(zero_counts_by_path.items(), key=lambda x: x[1], reverse=True)[:35]:
        print(f"  {p}: {c}")

run_inspection()
"""

if __name__ == "__main__":
    run_remote_python(code)
