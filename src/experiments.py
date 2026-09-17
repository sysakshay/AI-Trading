"""Saved, reproducible offline policy comparisons. Never invokes paid providers."""
import json
from .domain import Settings,identity
from .engine import now
from .research import import_research
from .ai import Reviewer
from .reporting import report

VARIANTS={'rules':dict(ai_mode='rules',regime_policy='observe'),
          'mock_research':dict(ai_mode='mock',regime_policy='observe'),
          'regime_filter':dict(ai_mode='rules',regime_policy='avoid_high_volatility')}

def compare(engine,source_run):
    source=engine.run(source_run)
    if source['mode']=='FORWARD': raise ValueError('Only frozen offline snapshots are supported; no live automatic approvals')
    cfg=Settings.model_validate_json(source['config'])
    research=engine.db.rows('SELECT payload FROM research_items WHERE run=? ORDER BY id',(source_run,))
    inputs=[json.loads(x['payload']) for x in research]
    manifest=dict(version='comparison-v1',source_run=source_run,data_hash=source['data_hash'],research_hash=identity(inputs),
        config=cfg.model_dump(),variants=VARIANTS,fill_policy='completed-close-v1',code_version='0.2.0',
        description='Same immutable data, starting capital, costs and risk bounds; each policy has its own constrained account. Not a causal estimate of AI value.')
    key=identity(manifest)
    with engine.db.transaction() as c:
        if c.execute('SELECT 1 FROM experiments WHERE id=?',(key,)).fetchone(): return key
        c.execute('INSERT INTO experiments VALUES(?,?,?,?,?,?,?)',(key,source_run,json.dumps(manifest),'RUNNING',now(),None,None))
    try:
        bars=engine.bars(source_run); schedule=json.loads(source['schedule'])
        for name,changes in VARIANTS.items():
            run=engine.create(bars,schedule,Settings(**{**cfg.model_dump(),**changes}),'BACKTEST')
            with engine.db.transaction() as c: c.execute('INSERT INTO experiment_runs VALUES(?,?,?)',(key,name,run))
            if inputs: import_research(engine.db,run,inputs)
            engine.backtest(run,Reviewer(engine) if changes['ai_mode']=='mock' else None)
        with engine.db.transaction() as c: c.execute("UPDATE experiments SET state='COMPLETE',completed=? WHERE id=?",(now(),key))
    except Exception as exc:
        with engine.db.transaction() as c: c.execute("UPDATE experiments SET state='FAILED',error=? WHERE id=?",(type(exc).__name__,key))
        raise
    return key

def experiment_report(db,key):
    rows=db.rows('SELECT * FROM experiments WHERE id=?',(key,))
    if not rows: raise ValueError('Unknown experiment')
    exp=rows[0]; manifest=json.loads(exp['manifest']); variants=[]
    for member in db.rows('SELECT * FROM experiment_runs WHERE experiment=? ORDER BY variant',(key,)):
        metrics=report(db,member['run'])
        variants.append(dict(variant=member['variant'],run=member['run'],trades=metrics['completed_trades'],
            net_paise=metrics['net_realized_paise'],drawdown_paise=metrics['max_drawdown_paise'],
            costs_paise=metrics['transaction_costs_paise'],sample=metrics['sample_assessment'],states=metrics['candidate_states']))
    matched=[]
    for member in db.rows('SELECT * FROM experiment_runs WHERE experiment=?',(key,)):
        for p in db.rows('SELECT instrument,time,state,reason FROM candidates WHERE run=? ORDER BY time,instrument',(member['run'],)):
            matched.append(dict(variant=member['variant'],**p))
    return dict(experiment=key,state=exp['state'],manifest=manifest,variants=variants,candidate_decisions=matched,
        limitations=['MOCK is a plumbing control, not an LLM forecast','Regime filtering is an unvalidated hypothesis; UNKNOWN blocks entries',
            'Cash-only reference has zero trading return; no equity benchmark data or alpha claim','Run portfolios can diverge under capacity constraints',
            'For development/test evaluation use separate chronological datasets; no automatic tuning performed'])
