import json
from datetime import timedelta
import pytest
from src.db import Database
from src.engine import Engine,uid
from src.domain import Settings,stamp
from src.data import sample,sample_schedule,exchange_schedule
from src.ai import Reviewer
from src.worker import Worker

def ready(tmp_path):
    e=Engine(Database(tmp_path/'more.db')); r=e.create(sample(),sample_schedule(),Settings(ai_mode='rules'))
    for _ in range(28): e.advance(r)
    return e,r

def test_missing_final_bar_blocks_next_day(tmp_path):
    e=Engine(Database(tmp_path/'gap.db'))
    bars=[b for b in sample() if not (b.instrument=='DEMO-WIN' and b.time=='2026-09-14T15:30:00+05:30')]
    r=e.create(bars,sample_schedule(),Settings(ai_mode='rules'))
    for _ in range(28):e.advance(r)
    assert not e.db.rows("SELECT * FROM candidates WHERE instrument='DEMO-WIN'")
    assert e.db.rows("SELECT * FROM events WHERE kind='DATA_GAP'")

def test_memory_bound_includes_losses_excludes_unknown(tmp_path):
    e,r=ready(tmp_path); p=e.db.rows('SELECT * FROM candidates')[0]; t=p['time']
    with e.db.transaction() as c:
        for index in range(24):
            candidate=uid(); closed=(stamp(t)-timedelta(minutes=25-index)).isoformat()
            if index==23: closed=(stamp(t)+timedelta(minutes=15)).isoformat()
            c.execute('INSERT INTO candidates(id,run,instrument,time,expiry,state,evidence,stop,target) VALUES(?,?,?,?,?,?,?,?,?)',
                (candidate,r,p['instrument'],closed,closed,'FILLED','{}',9000,12000))
            c.execute('INSERT INTO positions(id,run,instrument,candidate,qty,entry,entry_fee,stop,target,risk,opened,mark,marked,closed,exit,exit_fee) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (uid(),r,p['instrument'],candidate,1,10000,10,9000,12000,1000,'2026-09-14T12:00:00+05:30',10000,closed,closed,9900 if index%2 else 10100,10))
    context=Reviewer(e).context(p['id']); assert len(context['history'])==20
    assert context['history_stats']['losses']>0
    assert all(x['closed']<=t for x in context['history'])

def test_pending_reservations_and_stale_marks(tmp_path):
    e,r=ready(tmp_path); ps=e.db.rows('SELECT * FROM candidates ORDER BY instrument')
    e.decide(ps[0]['id'],1)
    with e.db.transaction() as c:
        a=e.account(c,r,e.run(r)['cursor']); assert a['reserved']>0; assert a['risk']<=10000
    e.advance(r)
    with e.db.transaction() as c:
        c.execute("UPDATE positions SET marked='2026-09-14T15:30:00+05:30' WHERE run=?",(r,))
        assert e.account(c,r,e.run(r)['cursor'])['stale']

def test_worker_offline_catchup_no_retroactive_entry(tmp_path,monkeypatch):
    e,r=ready(tmp_path); p=e.db.rows('SELECT * FROM candidates')[0]; e.decide(p['id'],1)
    at='2026-09-15T10:31:00+05:30'
    with e.db.transaction() as c:
        c.execute("UPDATE runs SET mode='FORWARD' WHERE id=?",(r,))
        c.execute('DELETE FROM candles WHERE run=? AND time>?',(r,'2026-09-15T10:30:00+05:30'))
    monkeypatch.setattr('src.worker.now',lambda:at); monkeypatch.setattr('src.engine.now',lambda:at)
    class Provider:
        def completed(self,*args): return []
    verified={k:True for k in ['data_rights_confirmed','unadjusted_verified','calendar_verified','no_corporate_actions']}
    verified.update(smoke_received_timestamp=at,measured_delay_seconds=30)
    w=Worker(e,Provider(),r,[],verified); w.once(at); w.once(at)
    assert not e.db.rows('SELECT * FROM fills')
    assert e.db.rows('SELECT state FROM orders')[0]['state']=='CANCELLED'
    assert e.db.rows('SELECT last_processed FROM worker')[0]['last_processed']=='2026-09-15T10:30:00+05:30'

def test_calendar_library_regular_and_holiday():
    calendar=exchange_schedule('2026-01-26','2026-01-27')
    assert '2026-01-26' not in calendar
    assert calendar['2026-01-27']['close'].endswith('15:30:00+05:30')

def test_daily_trade_limit_and_session_cutoff(tmp_path):
    e,r=ready(tmp_path); p=e.db.rows('SELECT * FROM candidates')[0]
    with e.db.transaction() as c: c.execute('UPDATE sessions SET trades=3 WHERE run=?',(r,))
    ok,reason=e.decide(p['id'],1); assert not ok; assert 'Daily' in reason
    assert not e.db.rows('SELECT * FROM orders')

def test_independent_cash_report_numbers(tmp_path):
    from src.reporting import report
    e,r=ready(tmp_path)
    for p in e.db.rows('SELECT * FROM candidates'): assert e.decide(p['id'],1)[0]
    e.advance(r); e.advance(r)
    result=report(e.db,r)
    # 24 shares each: entry 103.05, exits 99.95 and 106.35.
    # Gross (-3.10 + 3.30) * 24 = 4.80; fees 2.48+2.40+2.48+2.56=9.92.
    assert result['gross_closed_paise']==480
    assert result['transaction_costs_paise']==992
    assert result['net_realized_paise']==-512
    assert result['cash_paise']==999488

def test_missing_exit_observation_preserves_position(tmp_path):
    e,r=ready(tmp_path); p=e.db.rows("SELECT * FROM candidates WHERE instrument='DEMO-WIN'")[0]
    e.decide(p['id'],1); e.advance(r)
    pos=e.db.rows('SELECT * FROM positions')[0]; e.request_exit(pos['id'])
    with e.db.transaction() as c: c.execute('DELETE FROM candles WHERE run=? AND instrument=? AND time>?',(r,p['instrument'],e.run(r)['cursor']))
    e.advance(r)
    assert e.db.rows('SELECT closed FROM positions')[0]['closed'] is None
    with e.db.transaction() as c: assert e.account(c,r,e.run(r)['cursor'])['stale']
