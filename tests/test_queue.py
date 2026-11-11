import pytest
from traffic.queue import groups

def points(values,length=5):return [dict(front=p,length=length) for p in values]
def test_separated_jams_and_parallel_lanes_are_not_summed():
    assert groups(points([250,240,230,100,90]),10)==[25,15]
    assert groups(points([270,258,246]),10)==[29]
    assert max(max(groups(points(p),10)) for p in ([250,240,230,100,90],[270,258,246]))==29

def test_detector_clipping_empty_and_gap_boundary():
    assert groups([],10)==[]
    assert groups(points([3]),10,start=0,end=300)==[3]
    assert groups(points([305,295]),10,start=0,end=300)==[10]
    assert groups(points([100,85]),10)==[20]
    assert groups(points([100,84.9]),10)==pytest.approx([5,5])

