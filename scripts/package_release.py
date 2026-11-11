"""Package research app, frontend, public attribution and all experiment evidence."""
from pathlib import Path
import hashlib,json,zipfile
from traffic.io import write_json,sha256
ROOT=Path(__file__).resolve().parents[1]

def main():
    top={'app.py','README.md','requirements.txt','requirements-lock.txt','run.cmd','setup.cmd','.gitignore'}
    folders={'.streamlit','traffic','frontend','scripts','tests','docs','experiments','data','baseline','case_studies'}
    selected=[]
    for file in ROOT.rglob('*'):
        rel=file.relative_to(ROOT)
        if not file.is_file() or any(p in ('__pycache__','.pytest_cache') for p in rel.parts):continue
        if file.suffix in ('.pyc','.tmp'):continue
        if file.name in ('release_manifest_v3.json','release_package_v3.json','release_extraction_v3.json'):continue
        if (len(rel.parts)==1 and file.name in top) or rel.parts[0] in folders or (rel.parts[0]=='static' and rel.parts[1] in ('fonts','daegu')):selected.append(file)
    manifest={f.relative_to(ROOT).as_posix():dict(bytes=f.stat().st_size,sha256=sha256(f)) for f in selected}
    write_json(ROOT/'docs/release_manifest_v3.json',dict(files=manifest,excludes=['self manifest','post-package receipt','runtime','generated static replay copies','Python caches']))
    selected.append(ROOT/'docs/release_manifest_v3.json')
    target=ROOT.parent/'traffic-impact-research-v3-daegu.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
        for file in sorted(selected):z.write(file,Path(ROOT.name)/file.relative_to(ROOT))
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for required in ('run.cmd','setup.cmd','frontend/replay.js','frontend/city.js','static/daegu/geometry.json','static/fonts/OFL.txt','case_studies/daegu_beomeo/v1/derived_metrics.json','data/public/ngsim/ATTRIBUTION.md','docs/demo/traffic_comparison.mp4'):
            assert f'{ROOT.name}/{required}' in z.namelist(),required
        for name,expected in manifest.items():
            h=hashlib.sha256()
            with z.open(f'{ROOT.name}/{name}') as f:
                for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
            assert h.hexdigest()==expected['sha256'],name
    receipt=dict(path=str(target),files=len(selected),bytes=target.stat().st_size,sha256=sha256(target),crc_passed=True,all_manifest_hashes_matched=True)
    write_json(ROOT/'docs/release_package_v3.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':main()

