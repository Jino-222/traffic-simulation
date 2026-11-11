"""Verify the new archive in a fresh folder without rerunning completed studies."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys,zipfile
from traffic.io import write_json,sha256
ROOT=Path(__file__).resolve().parents[1]

def main():
    archive=ROOT.parent/'traffic-impact-research-v3-daegu.zip'
    dest=Path(os.environ['LOCALAPPDATA'])/'TrafficImpactLab/release-verification'/('city_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    dest.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():assert (dest/item.filename).resolve().is_relative_to(dest.resolve()),item.filename
        z.extractall(dest)
    copied=dest/ROOT.name
    manifest=json.loads((copied/'docs/release_manifest_v3.json').read_text(encoding='utf-8'))
    mismatches=[name for name,m in manifest['files'].items() if sha256(copied/name)!=m['sha256']]
    assert not mismatches,mismatches
    env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
    with (ROOT/'docs/release_city_smoke.log').open('w',encoding='utf-8') as log:
        result=subprocess.run([sys.executable,'-m','pytest','-q','tests/test_city.py','tests/test_app.py::test_app_default_load'],cwd=copied,env=env,stdout=log,stderr=subprocess.STDOUT)
    receipt={'archive':str(archive),'archive_sha256':sha256(archive),'extracted_to':str(copied),
             'manifest_files':len(manifest['files']),'hash_mismatches':mismatches,'copied_app_test_exit_code':result.returncode,
             'scope':'Same installed environment; copied-path smoke tests. No new clean-environment installation.'}
    write_json(ROOT/'docs/release_extraction_v3.json',receipt)
    assert result.returncode==0,'See docs/release_city_smoke.log'
    print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
