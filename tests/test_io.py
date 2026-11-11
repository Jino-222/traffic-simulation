from pathlib import Path
import json
from traffic.io import write_json

def test_atomic_write_retries_transient_lock(tmp_path,monkeypatch):
    target=tmp_path/"value.json"
    write_json(target,{"old":1})
    original=Path.replace
    calls=[]
    def flaky(self,destination):
        calls.append(1)
        if len(calls)==1: raise PermissionError("simulated OneDrive lock")
        return original(self,destination)
    monkeypatch.setattr(Path,"replace",flaky)
    write_json(target,{"new":2})
    assert len(calls)==2
    assert json.loads(target.read_text())=={"new":2}
