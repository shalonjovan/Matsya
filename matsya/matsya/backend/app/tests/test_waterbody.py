def test_waterbody():
    from app.services.hydro.waterbody import WaterBody
    wb=WaterBody(area_m2=50000, crest=5.0, stage=5.0)
    wb.inflow(10) # 10 m3/s for 300s
    out=wb.step(300)
    assert wb.volume > 0
    # when stage below crest, outflow 0
    wb2=WaterBody(area_m2=50000, crest=5.0, stage=4.5)
    # stage 4.5 is above bed (3.0) but below crest 5.0, so no outflow
    # need to set stage 4.5 which is below crest, but above bed, volume >0 but outflow 0
    assert wb2.step(300)==0
    # when empty (stage=bed), outflow 0
    wb3=WaterBody(area_m2=50000, crest=5.0, stage=3.0) # bed
    wb3.inflow(0)
    assert wb3.step(300)==0

def test_waterbody_weir():
    from app.services.hydro.waterbody import WaterBody
    wb=WaterBody(area_m2=10000, crest=5.0, stage=6.0) # head 1m
    out=wb.step(300)
    # Q = 1.7*10*1^1.5 = 17, outflow should be ~17
    assert abs(out - 17) < 1
    # after step, stage should have dropped
    assert wb.stage < 6.0
    assert wb.stage >= 5.0

def test_waterbody_mass():
    from app.services.hydro.waterbody import WaterBody
    wb=WaterBody(area_m2=10000, crest=5.0, stage=3.0) # empty
    wb.inflow(5)
    out1=wb.step(600) # 5*600=3000 inflow, no outflow because stage still below crest? stage = 3 + 3000/10000=3.3 <5, so outflow 0
    assert out1==0
    assert abs(wb.volume - 3000) < 1
    # now add more to exceed crest
    wb.inflow(10)
    out2=wb.step(600) # inflow 6000, volume 9000, stage=3.9 <5, still 0
    assert out2==0
    # now push above crest
    wb.inflow(20)
    out3=wb.step(600) # inflow 12000, volume 21000, stage=5.1, head 0.1, outflow ~1.7*10*0.0316=0.537
    assert out3>0
