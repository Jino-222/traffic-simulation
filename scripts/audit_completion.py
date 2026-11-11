"""Check completion gates against actual study records and the inspected source state."""
from pathlib import Path
import json,xml.etree.ElementTree as ET
from traffic.io import write_json,sha256
from traffic.search import core_hash
from traffic.research.network_runner import source_hash
ROOT=Path(__file__).resolve().parents[1]
def read(name):return json.loads((ROOT/name).read_text(encoding='utf-8'))

def main():
    requirements=read('docs/requirements.json')['requirements']
    assert all(r['status']=='complete' for r in requirements)
    checks={}
    for name in ('chart_values_audit','profile_mix_audit','completed_studies_audit','network_study_audit','search_lifecycle_audit',
                 'browser_validation','environment_audit','release_extraction','release_execution','release_web_audit'):
        a=read('docs/'+name+'.json');assert a['passed'],name;checks[name]=sha256(ROOT/'docs'/f'{name}.json')
    for name in ('baseline_audit','selected_replay_audit'):
        a=read('docs/'+name+'.json');assert a['matched'] and not a['differences'];checks[name]=sha256(ROOT/'docs'/f'{name}.json')
    video=read('docs/demo/video_audit.json');assert video['matched'] and video['frames_decoded']==600 and video['video_sha256']==sha256(ROOT/'docs/demo/traffic_comparison.mp4')
    tests={}
    for name in ('tests_release_candidate.xml','clean_environment_tests.xml'):
        suites=list(ET.parse(ROOT/'docs'/name).getroot().iter('testsuite'))
        assert sum(int(s.get('tests','0')) for s in suites)==83
        assert sum(int(s.get('failures','0'))+int(s.get('errors','0'))+int(s.get('skipped','0')) for s in suites)==0
        tests[name]=dict(tests=83,sha256=sha256(ROOT/'docs'/name))
    discovery=read('experiments/study_v2/discovery/search_summary.json')
    assert discovery['source_hash']==core_hash() and len(discovery['records'])==93
    holdout=read('experiments/study_v2/holdout/holdout_summary.json')
    assert holdout['frozen']['training_summary_hash']==sha256(ROOT/'experiments/study_v2/discovery/search_summary.json')
    assert set(holdout['frozen']['validation_seeds']).isdisjoint(holdout['frozen']['discovery_seeds'])
    network=read('experiments/network_study_v1/summary.json');assert network['protocol']['engine_sha256']==source_hash()
    assert network['discovery_runs']==33 and network['validation_runs']==6 and not network['validation_used_for_selection']
    assert read('docs/chart_values_audit.json')['plotted_source_hash']==sha256(ROOT/'traffic/dashboard.py')
    copied=Path(read('docs/release_extraction.json')['path'])
    runtime=[ROOT/'app.py',ROOT/'requirements.txt']+[f for folder in ('traffic','frontend','.streamlit') for f in (ROOT/folder).rglob('*') if f.is_file() and '__pycache__' not in f.parts]
    assert all(f.read_bytes()==(copied/f.relative_to(ROOT)).read_bytes() for f in runtime)
    for r in requirements:
        assert r['evidence']
        for file in r['evidence']:
            path=ROOT/file
            assert path.is_file() or (path.is_dir() and any(f.is_file() for f in path.rglob('*'))),file
    for name in ('research_report.md','advanced_research.md','network_research.md','profile_mix_research.md','contributions.md','final_audit.md'):
        assert (ROOT/'docs'/name).stat().st_size>1000
    write_json(ROOT/'docs/completion_audit.json',dict(passed=True,requirements=len(requirements),
        tests=tests,verified_gates=checks,exact_runtime_files=len(runtime),source_hash=core_hash(),network_engine_hash=source_hash(),
        evidence={r['id']:r['evidence'] for r in requirements},
        scope='Research prototype completion, not field safety/LOS validation or proof of the applicant personally doing the work.',
        final_package_gate='After this audit regenerate the final ZIP and check its embedded manifest against every archived payload.'))
    print(f'Completion gates passed: {len(requirements)} requirements,83 tests in two environments,{len(runtime)} identical runtime files')

if __name__=='__main__':main()
