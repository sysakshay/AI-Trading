import json,sqlite3
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import pytest
from src.domain import *
from src.data import sample,sample_schedule,csv_text
from src.db import Database
from src.engine import Engine
from src.ai import Reviewer,Review
from src.reporting import report,export_run

@pytest.fixture
def engine(tmp_path): return Engine(Database(tmp_path/'paper.db'))
def ready(e,mode='rules',bars=None,cfg=None):
    r=e.create(bars or sample(),sample_schedule(),cfg or Settings(ai_mode=mode))
    for _ in range(28): e.advance(r)
    if mode!='rules': Reviewer(e).review_pending(r)
    return r
def candidates(e,r): return e.db.rows('SELECT * FROM candidates WHERE run=? ORDER BY instrument',(r,))
def reconcile(e,r):
    cash=e.run(r)['cash']; assert cash==sum(x['amount'] for x in e.db.rows('SELECT amount FROM ledger WHERE run=?',(r,)))
    fills=e.db.rows('SELECT * FROM fills WHERE run=?',(r,)); ledger=e.db.rows('SELECT * FROM ledger WHERE run=? AND fill IS NOT NULL',(r,))
    assert len(fills)==len(ledger)
    assert cash>=0

def test_indicator_known_fixture():
    bars=[b for b in sample() if b.instrument=='DEMO-WIN'][:25]
    result=evaluate(bars,Settings())
    assert result['sma']==10072.5
    assert result['prior_sma']==10057.5
    assert result['atr']==100
    assert result['previous_high']==10165
    assert not result['breakout']
    assert not evaluate(bars[:22],Settings())['eligible']

def test_exclude_current_and_determinism():
    bars=[b for b in sample() if b.instrument=='DEMO-WIN'][:28]
    a=evaluate(bars,Settings()); assert a['eligible']; assert a['volume_mean']==10000
    assert a['volume_ratio']==2.5; assert a==evaluate(bars,Settings())
    assert a['previous_high']<bars[-1].close

@pytest.mark.parametrize('change',[{'low':0},{'high':1},{'volume':-1},{'end':'2026-09-14T09:30:00'},{'interval':5},{'close':float('nan')}])
def test_candle_validation(change):
    payload=sample()[0].model_dump(); payload.update(change)
    with pytest.raises(ValueError): Candle(**payload)

def test_csv_row_errors_and_missing_volume():
    text=csv_text(sample()[:5]); bars,errors=import_csv(text); assert len(bars)==5 and not errors
    text=text.replace(',10000,',',,',1); assert import_csv(text)[1]
    assert import_csv('open,close\n1,2')[1]

def test_duplicates_order_and_gap(engine):
    bars=sample(); assert import_csv(csv_text([bars[0],bars[0]]))[1]
    instrument=[b for b in bars if b.instrument=='DEMO-WIN']
    assert import_csv(csv_text([instrument[1],instrument[0]]))[1]
    assert 'Missing' in evaluate(instrument[:10]+instrument[11:28],Settings())['reason']
    with pytest.raises(ValueError): engine.create([bars[0],bars[0]],sample_schedule())

def test_size_independent_boundaries():
    cfg=Settings(fee_bps=0,slip_bps=0)
    assert size(10000,9900,10200,100000,1000000,1000000,0,cfg)[0]==50
    assert size(10000,9900,10200,100000,9999,1000000,0,cfg)[0]==0
    assert size(10000,9900,10200,100000,1000000,1000000,10000,cfg)[0]==0
    assert size(10000,9900,10200,50,1000000,1000000,0,cfg)[0]==0
    assert size(10000,10000,10200,100000,1000000,1000000,0,cfg)[0]==0
    assert fee(10001,3,Settings(fee_bps=10))==31

def test_complete_offline_restart_and_reconcile(engine):
    r=ready(engine,'mock'); p=candidates(engine,r)[1]
    assert engine.decide(p['id'],1)[0]; assert not engine.db.rows('SELECT * FROM fills')
    with engine.db.transaction() as c: assert engine.account(c,r,engine.run(r)['cursor'])['reserved']>0
    engine=Engine(Database(engine.db.path)); engine.advance(r)
    pos=engine.db.rows('SELECT * FROM positions')[0]; assert pos['opened']>p['time']; reconcile(engine,r)
    engine.advance(r); rep=report(engine.db,r); assert rep['completed_trades']==1; assert rep['net_realized_paise']>0
    reconcile(engine,r); assert Engine(Database(engine.db.path)).run(r)['cash']==engine.run(r)['cash']

def test_double_concurrent_approval(engine):
    r=ready(engine); p=candidates(engine,r)[0]
    with ThreadPoolExecutor(2) as pool: results=list(pool.map(lambda _:engine.decide(p['id'],1),range(2)))
    assert sum(x[0] for x in results)==1
    engine.advance(r); assert len(engine.db.rows('SELECT * FROM fills'))==1
    assert len(engine.db.rows('SELECT * FROM decisions'))==1

def test_expiry_revision_rejection(engine):
    r=ready(engine); p=candidates(engine,r)[0]
    with pytest.raises(ValueError): engine.decide(p['id'],2)
    assert not engine.decide(p['id'],1,at=p['expiry'])[0]
    p=candidates(engine,r)[1]; assert engine.decide(p['id'],1,False)[0]
    assert not engine.db.rows('SELECT * FROM orders'); reconcile(engine,r)

def test_gap_and_both_stop_first(engine):
    r=ready(engine); p=candidates(engine,r)[0]; engine.decide(p['id'],1); engine.advance(r); engine.advance(r)
    pos=engine.db.rows('SELECT * FROM positions')[0]; assert pos['exit']==9995; assert pos['exit']<pos['stop']
    bars=sample()
    bars=[b.model_copy(update={'high':11000}) if b.instrument=='DEMO-LOSS' and b.time=='2026-09-15T10:30:00+05:30' else b for b in bars]
    r=ready(engine,bars=bars); engine.decide(candidates(engine,r)[0]['id'],1); engine.advance(r); engine.advance(r)
    pos=engine.db.rows('SELECT * FROM positions WHERE run=?',(r,))[0]; assert pos['exit']==9995

def test_original_level_crossed_and_cash_released(engine):
    bars=[b.model_copy(update={'close':11000,'high':11100}) if b.time=='2026-09-15T10:15:00+05:30' else b for b in sample()]
    r=ready(engine,bars=bars); engine.decide(candidates(engine,r)[0]['id'],1); engine.advance(r)
    assert not engine.db.rows('SELECT * FROM fills')
    assert engine.db.rows('SELECT state FROM orders')[0]['state']=='CANCELLED'; reconcile(engine,r)

def test_pause_keeps_exits(engine):
    r=ready(engine); engine.decide(candidates(engine,r)[1]['id'],1); engine.advance(r); engine.pause(r,True); engine.advance(r)
    assert report(engine.db,r)['completed_trades']==1

def test_latched_halt_and_exit_during_ai_failure(engine):
    cfg=Settings(ai_mode='rules',daily_loss=.001)
    r=ready(engine,cfg=cfg)
    for p in candidates(engine,r): engine.decide(p['id'],1)
    engine.advance(r)
    with engine.db.transaction() as c:
        c.execute('UPDATE sessions SET equity=2000000 WHERE run=?',(r,))
    engine.advance(r)
    assert engine.db.rows('SELECT MAX(halted) h FROM sessions WHERE run=?',(r,))[0]['h']==1
    assert report(engine.db,r)['completed_trades']==2
    engine.advance(r); assert engine.db.rows("SELECT halted FROM sessions WHERE run=? AND day='2026-09-15'",(r,))[0]['halted']==1

def test_failed_mock_blocks_entries(engine):
    r=ready(engine,'mock_fail'); assert all(p['state']=='FAILED' for p in candidates(engine,r))
    for p in candidates(engine,r): assert not engine.decide(p['id'],1)[0]
    assert not engine.db.rows('SELECT * FROM orders')

def test_memory_immutable_future_safe(engine):
    r=ready(engine,'mock'); p=candidates(engine,r)[0]
    saved=engine.db.rows('SELECT context FROM reviews WHERE candidate=?',(p['id'],))[0]['context']
    engine.decide(p['id'],1); engine.advance(r); engine.advance(r)
    assert Reviewer(engine).review(p['id'])['context']==saved
    assert json.loads(saved)['history']==[]
    assert all(stamp(b['end'])<=stamp(p['time']) for b in json.loads(saved)['recent_bars'])
    with pytest.raises(ValueError): Reviewer(engine).context(p['id'])

def test_strict_ai_schema():
    valid=dict(candidate_id='a',decision='WATCH',supporting_factors=[],risk_factors=['Insufficient evidence'],summary='Wait')
    assert Review(**valid)
    for changes in [{'decision':'BUY'},{'confidence':.9},{'summary':'x'*1001},{'candidate_id':12}]:
        with pytest.raises(ValueError): Review(**{**valid,**changes})

def test_budget_missing_key_and_no_request(engine,monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    r=ready(engine,'rules',cfg=Settings(ai_mode='openai'))
    for p in candidates(engine,r):
        result=Reviewer(engine).review(p['id']); assert result['error']=='MISSING_KEY'; assert result['allowance']==0

def test_modes_isolated_and_deterministic(engine):
    results=[]
    for _ in range(2):
        r=engine.create(sample(),sample_schedule(),Settings(ai_mode='rules'),'BACKTEST'); engine.backtest(r); rep=report(engine.db,r)
        results.append((rep['net_realized_paise'],rep['completed_trades'],rep['transaction_costs_paise']))
    assert results[0]==results[1]; assert results[0][1]==2

def test_backup_restore_and_exports(engine,tmp_path,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','SECRET_MUST_NOT_APPEAR')
    r=ready(engine); engine.decide(candidates(engine,r)[0]['id'],1); engine.advance(r)
    backup=engine.db.backup(tmp_path/'backup.db'); Database.restore(backup,tmp_path/'restored.db')
    restored=Engine(Database(tmp_path/'restored.db')); reconcile(restored,r)
    assert 'SECRET_MUST_NOT_APPEAR' not in export_run(engine.db,r)
    with pytest.raises(ValueError): Database.restore(backup,tmp_path/'restored.db')

def test_zero_trade_metrics(engine):
    r=engine.create(sample(),sample_schedule()); rep=report(engine.db,r)
    assert rep['win_rate'] is None and rep['profit_factor'] is None and rep['expectancy_paise'] is None

def test_transaction_rolls_back(engine):
    r=ready(engine); cash=engine.run(r)['cash']
    with pytest.raises(RuntimeError):
        with engine.db.transaction() as c:
            c.execute('UPDATE runs SET cash=0 WHERE id=?',(r,)); raise RuntimeError('simulated crash')
    assert engine.run(r)['cash']==cash

def test_calendar_holiday_rejected(engine):
    b=sample()[0].model_copy(update={'end':stamp('2026-09-13T09:30:00+05:30')})
    with pytest.raises(ValueError): engine.create([b],sample_schedule())
