from pathlib import Path
import json,zipfile,hashlib
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output'
files=[]
for folder in ['data','network','runs','figures','web']:
    files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
files.extend(p for p in ROOT.iterdir() if p.is_file() and p.suffix in ['.py','.txt','.cmd'])
names=['daegu_comparison_replay.mp4','scenario_metrics.csv','edge_metrics.csv','validation.json','audit.json','first_signal_load_failure.log','09_native_sumo_overview_manifest.json','10_native_sumo_closeup_manifest.json','gallery_verified.png','gallery_isometric_verified.png','UI_CHECKS.txt']
files.extend(OUT/n for n in names if (OUT/n).exists())
manifest={str(p.relative_to(ROOT)).replace('\\','/'):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files}
(OUT/'release_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
files.append(OUT/'release_manifest.json')
target=OUT/'Daegu_SUMO_Visualization_Complete.zip'
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in files:z.write(p,str(p.relative_to(ROOT)))
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    for name,item in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==item['sha256']
result={'file':target.name,'files':len(files),'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'zip_crc_and_all_manifest_hashes':'passed'}
(OUT/'release_check.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
