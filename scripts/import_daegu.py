"""Import a frozen city study without modifying the source or running SUMO."""
from pathlib import Path
import argparse,shutil,json,hashlib
from traffic.city import ROOT,CASE,derive
from traffic.io import write_json,sha256

def main(source):
    source=Path(source).resolve()
    if CASE.exists():raise SystemExit('Frozen city case already exists. Use a new version directory for new results.')
    CASE.mkdir(parents=True)
    copied={}
    for p in source.rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(source)
        if '__pycache__' in rel.parts or p.suffix in ('.zip','.pyc') or 'server' in p.name:continue
        dest=CASE/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
        copied[rel.as_posix()]=sha256(dest)
    write_json(CASE/'import_manifest.json',{'origin':str(source),'files':copied,'policy':'Original evidence copied byte-for-byte. Derived cohort metrics are separate.'})
    write_json(CASE/'derived_metrics.json',derive())
    static=ROOT/'static/daegu';static.mkdir(parents=True,exist_ok=True)
    for p in (CASE/'web').glob('*.json'):shutil.copy2(p,static/p.name)
    write_json(ROOT/'docs/daegu_import_audit.json',{'files':len(copied),'all_hashes_match':all(sha256(CASE/n)==h for n,h in copied.items()),'case':'case_studies/daegu_beomeo/v1'})
    print(json.dumps({'files':len(copied),'cohorts':{k:{s:v['counts'] for s,v in m.items()} for k,m in derive()['scopes'].items()}},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');main(p.parse_args().source)
