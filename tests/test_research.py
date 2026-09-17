import json,sqlite3
from pathlib import Path
from datetime import timedelta
import pytest
from src.db import Database
from src.engine import Engine
from src.domain import Settings,stamp,evaluate
from src.data import sample,sample_schedule
from src.research import ResearchItem,regime,research_packet,import_research,known_items
from src.experiments import compare,experiment_report
from src.reporting import report,add_expense,export_run

def make(tmp_path,cfg=None):
    e=Engine(Database(tmp_path/'research.db')); r=e.create(sample(),sample_schedule(),cfg or Settings(ai_mode='rules'))
    return e,r

def ready(e,r):
    for _ in range(28):e.advance(r)

def source(**changes):
    return {**json.loads(Path('fixtures/research-example.json').read_text())[0],**changes}

def test_timestamped_evidence_and_snapshot_freeze(tmp_path):
    e,r=make(tmp_path)
    raw=[source(),source(title='Not yet available',available_at='2026-09-15T10:01:00+05:30'),source(title='Future story',published_at='2026-09-15T11:00:00+05:30',available_at='2026-09-15T11:01:00+05:30')]
    assert import_research(e.db,r,raw)==3
    assert import_research(e.db,r,raw)==0
    ready(e,r)
    candidate=e.db.rows("SELECT * FROM candidates WHERE instrument='DEMO-WIN'")[0]
    research=json.loads(candidate['evidence'])['research']
    assert research['coverage']=={'news':1,'fundamentals':0}
    assert len(research['sources'])==1
    assert research['sources'][0]['title'].startswith('SYNTHETIC')
    with pytest.raises(ValueError,match='before'): import_research(e.db,r,[source(title='Later correction')])
    e.advance(r)
    assert e.db.rows('SELECT evidence FROM candidates WHERE id=?',(candidate['id'],))[0]['evidence']==candidate['evidence']

@pytest.mark.parametrize('change',[{'available_at':'2026-09-15T09:00:00+05:30'},{'published_at':'2026-09-15T09:30:00'},{'source_url':'file:///secrets'},{'kind':'prediction'},{'confidence':.95}])
def test_research_validation(change):
    with pytest.raises(ValueError): ResearchItem.model_validate(source(**change))

def test_import_atomic_and_no_forward_backdating(tmp_path):
    e,r=make(tmp_path)
    with pytest.raises(ValueError): import_research(e.db,r,[source(),source(instrument='WRONG')])
    assert not e.db.rows('SELECT * FROM research_items')
    with e.db.transaction() as c:c.execute("UPDATE runs SET mode='FORWARD' WHERE id=?",(r,))
    with pytest.raises(ValueError,match='replay-only'):import_research(e.db,r,[source()])

def test_regime_prior_only_and_warmup():
    bars=[b for b in sample() if b.instrument=='DEMO-WIN']; cfg=Settings()
    assert regime(bars[:34],cfg)['label']=='UNKNOWN'
    base=bars[0]
    bars=[base.model_copy(update={'end':base.end+timedelta(minutes=15*i),'open':10000,'high':10050,'low':9950,'close':10000}) for i in range(40)]
    result=regime(bars,cfg)
    assert result['label']=='RANGE' and result['lower']==.01 and result['upper']==.01
    shock=bars[-1].model_copy(update={'high':10400,'low':9600})
    result=regime(bars[:-1]+[shock],cfg)
    assert result['label']=='HIGH_VOLATILITY'; assert result['upper']==.01
    assert result['atr_fraction']==pytest.approx(.015)

def test_research_does_not_change_default_fills(tmp_path):
    e,r=make(tmp_path); e.backtest(r); metrics=report(e.db,r)
    assert metrics['net_realized_paise']==-512
    assert metrics['regime_breakdown'][0]['regime']=='UNKNOWN'
    assert sum(x['trades'] for x in metrics['regime_breakdown'])==2
    p=e.db.rows('SELECT evidence FROM candidates')[0]
    research=json.loads(p['evidence'])['research']
    assert research['bull_case'] and research['bear_case']
    assert research['missing_evidence'] and research['risk_review']['entry_policy_passed']

def test_opt_in_regime_gate_changes_version_not_risk(tmp_path):
    cfg=Settings(ai_mode='rules',regime_policy='avoid_high_volatility')
    e,r=make(tmp_path,cfg); e.backtest(r)
    assert report(e.db,r)['completed_trades']==0
    assert all('UNKNOWN' in p['reason'] for p in e.db.rows('SELECT * FROM candidates'))
    assert cfg.version!=Settings(ai_mode='rules').version
    assert cfg.risk==.005

def test_saved_experiment_reproducibility_and_no_paid_calls(tmp_path,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','DO_NOT_USE')
    e,r=make(tmp_path,Settings(ai_mode='openai'))
    first=compare(e,r); result=experiment_report(e.db,first)
    assert result['state']=='COMPLETE'
    assert len(result['variants'])==3
    assert {x['variant']:x['net_paise'] for x in result['variants']}=={'rules':-512,'mock_research':-512,'regime_filter':0}
    assert not e.db.rows("SELECT * FROM reviews WHERE allowance>0")
    count=len(e.db.rows('SELECT * FROM runs'))
    restarted=Engine(Database(e.db.path))
    assert compare(restarted,r)==first
    assert len(e.db.rows('SELECT * FROM runs'))==count
    assert experiment_report(restarted.db,first)==result

def test_period_end_does_not_leak_future_cash_or_closed_positions(tmp_path):
    e,r=make(tmp_path); e.backtest(r)
    period=report(e.db,r,'2026-09-15T10:15:00+05:30','2026-09-15T10:30:00+05:30')
    assert period['completed_trades']==0 and period['open_positions']==2
    assert period['cash_paise']==1000000-2*(10305*24+248)
    assert period['transaction_costs_paise']==496
    assert period['closed_trade_costs_paise']==0
    assert len(period['equity_curve'])==1
    assert period['unrealized_paise']==-736
    assert period['ending_equity_paise']==999264
    day1=report(e.db,r,'2026-09-14T00:00:00+05:30','2026-09-15T00:00:00+05:30')
    assert day1['cash_paise']==1000000 and day1['max_drawdown_paise']==0

def test_saved_expense_no_cash_change_and_idempotency(tmp_path):
    e,r=make(tmp_path); ready(e,r)
    add_expense(e.db,r,'DATA',1500,'Weekly allocation',key='one-expense')
    add_expense(e.db,r,'DATA',1500,'Weekly allocation',key='one-expense')
    result=report(e.db,r)
    assert result['operating_costs_paise']==1500 and result['economic_realized_paise']==-1500
    assert e.run(r)['cash']==1000000
    assert 'Weekly allocation' in export_run(e.db,r)
    with pytest.raises(ValueError):add_expense(e.db,r,'DATA',-1)

def test_schema_one_upgrade_and_backup(tmp_path):
    path=tmp_path/'old.db'; c=sqlite3.connect(path)
    c.executescript(Path('src/schema.sql').read_text()); c.execute('PRAGMA user_version=1'); c.close()
    db=Database(path)
    assert db.rows('PRAGMA user_version')[0]['user_version']==2
    assert len(list(tmp_path.glob('old.before-v2-*.db')))==1
    assert db.rows('SELECT * FROM experiments')==[]
    Database(path)
    assert len(list(tmp_path.glob('old.before-v2-*.db')))==1

def test_worker_slow_fetch_uses_receive_time(tmp_path,monkeypatch):
    from src.worker import Worker
    e,r=make(tmp_path); ready(e,r)
    p=e.db.rows('SELECT * FROM candidates')[0]; e.decide(p['id'],1)
    with e.db.transaction() as c:
        c.execute("UPDATE runs SET mode='FORWARD' WHERE id=?",(r,))
        c.execute('DELETE FROM candles WHERE run=? AND time>?',(r,'2026-09-15T10:15:00+05:30'))
    clock=['2026-09-15T10:15:10+05:30']
    monkeypatch.setattr('src.worker.now',lambda:clock[0]); monkeypatch.setattr('src.engine.now',lambda:clock[0])
    class SlowProvider:
        def completed(self,*args): clock[0]='2026-09-15T10:17:10+05:30'; return []
    verification={k:True for k in ['data_rights_confirmed','unadjusted_verified','calendar_verified','no_corporate_actions']}
    verification.update(smoke_received_timestamp=clock[0],measured_delay_seconds=10)
    Worker(e,SlowProvider(),r,[{}],verification).once()
    assert not e.db.rows('SELECT * FROM fills')
    assert e.db.rows('SELECT state FROM orders')[0]['state']=='CANCELLED'
    assert e.db.rows('SELECT last_fetch FROM worker')[0]['last_fetch']==clock[0]

def test_worker_lost_lease_cannot_clear_other_owner(tmp_path,monkeypatch):
    from src.worker import Worker
    e,r=make(tmp_path)
    with e.db.transaction() as c:c.execute("UPDATE runs SET mode='FORWARD' WHERE id=?",(r,))
    at='2026-09-15T10:00:10+05:30'; monkeypatch.setattr('src.worker.now',lambda:at)
    verification={k:True for k in ['data_rights_confirmed','unadjusted_verified','calendar_verified','no_corporate_actions']}
    verification.update(smoke_received_timestamp=at,measured_delay_seconds=10)
    class ReplacedWorker:
        def completed(self,*args):
            with e.db.transaction() as c:c.execute("UPDATE worker SET lease_owner='new-owner' WHERE run=?",(r,))
            return []
    with pytest.raises(RuntimeError,match='lease lost'):Worker(e,ReplacedWorker(),r,[{}],verification).once()
    assert e.db.rows('SELECT lease_owner FROM worker')[0]['lease_owner']=='new-owner'
    assert not e.run(r)['paused']
