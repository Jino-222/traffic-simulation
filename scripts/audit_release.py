"""Extract the distributable safely, verify every manifest hash and test the copied app."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys,zipfile
from traffic.io import write_json,sha256
ROOT=Path(__file__).resolve().parents[1]

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def main():
    archive=ROOT.parent/'traffic-impact-research-v2.zip'
    dest=Path(os.environ['LOCALAPPDATA'])/'TrafficImpactLab/release-verification'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    dest.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            target=(dest/item.filename).resolve()
            assert target.is_relative_to(dest.resolve()),item.filename
        z.extractall(dest)
    copied=dest/ROOT.name
    manifest=json.loads((copied/'docs/release_manifest.json').read_text(encoding='utf-8'))
    mismatches=[name for name,m in manifest['files'].items() if digest(copied/name)!=m['sha256']]
    write_json(ROOT/'docs/release_extraction.json',dict(path=str(copied),archive_sha256=digest(archive),
        manifest_files=len(manifest['files']),mismatches=mismatches,passed=not mismatches))
    assert not mismatches,mismatches
    test_python=Path(os.environ['LOCALAPPDATA'])/'TrafficImpactLab/release-check-venv/Scripts/python.exe'
    env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
    with (ROOT/'docs/clean_environment_tests.log').open('w',encoding='utf-8') as log:
        result=subprocess.run([str(test_python),'-X','utf8','-m','pytest','-q','--junitxml='+str(ROOT/'docs/clean_environment_tests.xml')],cwd=copied,env=env,stdout=log,stderr=subprocess.STDOUT)
    write_json(ROOT/'docs/release_execution.json',dict(path=str(copied),python=str(test_python),
        tests_exit_code=result.returncode,passed=result.returncode==0,archive_sha256=digest(archive)))
    assert result.returncode==0,'Inspect clean_environment_tests.log'
    print(json.dumps(dict(path=str(copied),manifest_files=len(manifest['files']),all_hashes_match=True,tests_exit_code=0),ensure_ascii=False))

if __name__=='__main__':main()
