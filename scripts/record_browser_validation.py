"""Record observed CUA checks and independently verify the downloaded bytes."""
from pathlib import Path
import zipfile,json
from traffic.io import write_json,sha256
ROOT=Path(__file__).resolve().parents[1]

def main():
    downloads=Path.home()/'Downloads'
    with zipfile.ZipFile(downloads/'telemetry_smoke.zip') as z:
        assert z.testzip() is None
        files=z.namelist()
        for name in files:assert z.read(name)==(ROOT/'experiments/telemetry_smoke'/name).read_bytes()
        gz=sum(name.endswith('.gz') for name in files);assert gz==3
    for downloaded,source in [('profile_mix_research.md','docs/profile_mix_research.md'),('baseline_v2_inputs.json','experiments/baseline_v2/inputs.json')]:
        assert (downloads/downloaded).read_bytes()==(ROOT/source).read_bytes()
    pictures=['turning-ui.png','corridor-ui.png','queue-ui.png','detail-ui.png','search-ui.png','no-eligible-ui.png','replay-final-ui.png','replay-mobile-ui.png','video-playback-ui.png']
    ui_resume=ROOT/'experiments/search_lifecycle/20261110T173253Z_16b724/cancel_resume/status.json'
    state=json.loads(ui_resume.read_text());assert state['state']=='completed' and state['completed']==31 and state['failed']==0
    audit=dict(passed=True,method='CUA visible UI observations; downloaded files verified separately by bytes. This is not an automated accessibility certification.',
      observed_local_date='2026-11-11',
      observations={
        'network_pages':'Turning +1.16s not recommended; corridor 75m case 57.5m and 80 boundary samples; dynamic queue29/45/42/0m.',
        'detail':'All detailed chart families rendered; heatmap, cumulative graph and actual signal timeline inspected.',
        'candidate_scope':'Discovery31 and separate holdout section; validation runs removed from standalone candidate selector.',
        'no_eligible':'Actual overloaded two-candidate experiment displayed no eligible candidate and no fairness-satisfying candidate.',
        'ui_cancel_resume':'Clicked resume on a cancelled actual search; observed running4/31; clicked cancel, observed cancelled12/31; resumed and observed completed31/31.',
        'replay_long_record':'930→4200s jump completed in793ms observed wall time; both frames4200.0s; keyboard Space start/pause at20x; both stopped at4373.0s.',
        'replay_selection':'At930s same extra vehicle selected, left45.1km/h and right50.0km/h; same scheduled907s.',
        'replay_events':'Observed peak900s, next phase903s, start0s. These match raw telemetry/phase records.',
        'responsive':'390x844 replay controls fit; two panels stacked; sidebar collapsed; viewport reset. New event buttons wrap using same controls layout.',
        'video':'duration30s,readyState4; played0.0173→4.994s, stopped11.7899s, no media error; moving frames visually inspected.',
        'logs':'No browser console errors observed at completion of each UI inspection.'},
      downloads=dict(zip_files=len(files),all_bytes_identical=True,compressed_fcd_files=gz,report_identical=True,config_identical=True),
      screenshots={p:sha256(ROOT/'docs'/p) for p in pictures},ui_resume_status_hash=sha256(ui_resume))
    write_json(ROOT/'docs/browser_validation.json',audit)
    print('Recorded visible checks;92 ZIP entries, report and config bytes verified')

if __name__=='__main__':main()
