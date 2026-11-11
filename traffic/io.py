from pathlib import Path
import json, hashlib, time, uuid

def write_json(path, value):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+"."+uuid.uuid4().hex[:8]+".tmp")
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    for attempt in range(9):
        try:
            temp.replace(path)
            return
        except PermissionError:
            if attempt==8: raise
            time.sleep(min(.05*(2**attempt),.5))

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

