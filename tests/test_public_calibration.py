import numpy as np
import pandas as pd
import pytest
from traffic.research.public_calibration import prepare_trace,metrics

def test_preprocessing_preserves_targets_and_reports_monotonic_correction():
    d=pd.DataFrame(dict(global_time=[0,100,200,300],local_y_m_lead=[100,99,99.02,98],
        local_y_m=[110,109,109.02,108],speed_mps=[10,9,0,10],speed_mps_lead=[10,10,0,10],
        space_headway_m=[10]*4,v_length_m_lead=[5]*4,v_length_m=[4]*4))
    t=prepare_trace(d)
    assert t['leader'].tolist()==[0,1,1,2]
    assert t['observed_speed'].tolist()==[10,9,0,10]
    assert t['observed_gap'].tolist()==[5]*4
    assert t['quality']['monotonic_adjustment_max_m']==pytest.approx(.02)
    assert t['quality']['backward_intervals']==1
    d.loc[2,'global_time']=250
    with pytest.raises(ValueError,match='100 ms'):prepare_trace(d)

def test_rmse_objective_has_fixed_units_and_equal_trajectory_inputs():
    m=metrics([0,0],[2,2],[5,5],[15,15])
    assert m['speed_rmse_mps']==2 and m['gap_rmse_m']==10 and m['score']==2
    assert m['gap_bias_m']==10
    with pytest.raises(ValueError):metrics([],[],[],[])

def test_follower_future_measurements_are_not_fed_back_into_simulation(tmp_path):
    from traffic.research.public_calibration import make_network,simulate,BASELINE
    n=31;t=np.arange(n)*.1
    d=pd.DataFrame(dict(global_time=np.arange(n)*100,local_y_m_lead=100+t*3,local_y_m=80+t*3,
        speed_mps=np.full(n,3.),speed_mps_lead=np.full(n,3.),space_headway_m=np.full(n,20.),
        v_length_m_lead=np.full(n,5.),v_length_m=np.full(n,5.)))
    segment=dict(follower=1,file='trace.csv')
    net=make_network(tmp_path/'network',[segment])
    d.to_csv(tmp_path/'trace.csv',index=False)
    a=simulate(BASELINE,[segment],tmp_path,net,tmp_path/'a',True)
    d.loc[1:,'speed_mps']=10
    d.to_csv(tmp_path/'trace.csv',index=False)
    b=simulate(BASELINE,[segment],tmp_path,net,tmp_path/'b',True)
    pa=pd.read_csv(tmp_path/'a/predictions.csv');pb=pd.read_csv(tmp_path/'b/predictions.csv')
    assert a['valid'] and b['valid'] and a['leader_position_max_error_m']<1e-6
    assert np.allclose(pa.predicted_speed_mps,pb.predicted_speed_mps)
    assert np.allclose(pa.predicted_gap_m,pb.predicted_gap_m)
    assert not np.allclose(pa.predicted_speed_mps,pa.observed_speed_mps)
    assert a['mean_score']!=b['mean_score']
