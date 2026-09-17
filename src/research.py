"""Independent implementation of evidence-led research lenses; no paid calls or orders."""
import json
from datetime import datetime, timedelta
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator
from .domain import stamp, identity, evaluate

VERSION='research-v1'

class ResearchItem(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True)
    instrument: str=Field(min_length=1,max_length=80)
    kind: Literal['news','fundamentals']
    title: str=Field(min_length=1,max_length=160)
    summary: str=Field(min_length=1,max_length=600)
    source_url: HttpUrl
    published_at: datetime
    available_at: datetime
    @model_validator(mode='after')
    def timestamps(self):
        if stamp(self.available_at)<stamp(self.published_at): raise ValueError('Available time cannot precede publication')
        if self.source_url.username or self.source_url.password or self.source_url.query or self.source_url.fragment:
            raise ValueError('Use a public source URL without credentials, query parameters or fragments')
        return self

def import_research(db,run,raw):
    """Batch validation; preserve snapshots, never fetch links or execute their content."""
    if not isinstance(raw,list) or len(raw)>200: raise ValueError('Expected a list of at most 200 items')
    items=[ResearchItem.model_validate(x) for x in raw]
    with db.transaction() as c:
        r=c.execute('SELECT * FROM runs WHERE id=?',(run,)).fetchone()
        if not r: raise ValueError('Unknown run')
        if r['mode']=='FORWARD': raise ValueError('Historical imports are replay-only; forward evidence needs verified ingestion timestamps')
        if c.execute('SELECT 1 FROM candidates WHERE run=?',(run,)).fetchone():
            raise ValueError('Import before the first candidate; create a new run to change research inputs')
        for item in items:
            if not c.execute('SELECT 1 FROM candles WHERE run=? AND instrument=?',(run,item.instrument)).fetchone(): raise ValueError('Instrument not in this run')
        count=0
        for item in items:
            payload=item.model_dump(mode='json'); key=identity([run,payload])
            count+=c.execute('INSERT OR IGNORE INTO research_items VALUES(?,?,?,?,?,?,?)',
                (key,run,item.instrument,stamp(item.published_at).isoformat(),stamp(item.available_at).isoformat(),item.kind,json.dumps(payload))).rowcount
        return count

def known_items(c,run,instrument,asof):
    t=stamp(asof); lower=(t-timedelta(days=30)).isoformat()
    rows=c.execute('SELECT id,payload FROM research_items WHERE run=? AND instrument=? AND published<=? AND available<=? AND published>=? ORDER BY available DESC,id LIMIT 8',
        (run,instrument,t.isoformat(),t.isoformat(),lower)).fetchall()
    return [dict(id=x['id'],**json.loads(x['payload'])) for x in rows]

def regime(bars,cfg):
    """Wilder ATR/close versus 20 preceding ATR/close values; current excluded."""
    need=cfg.atr_period+21
    base=dict(version='regime-v1',label='UNKNOWN',trend='UNKNOWN',atr_fraction=None,
              lower=None,upper=None,reference_count=0,reason=f'Requires {need} contiguous completed bars')
    if len(bars)<need: return base
    if not evaluate(bars,cfg).get('atr'): return {**base,'reason':'Invalid/gapped technical history'}
    tr=[max(b.high-b.low,abs(b.high-a.close),abs(b.low-a.close)) for a,b in zip(bars,bars[1:])]
    atr=sum(tr[:cfg.atr_period])/cfg.atr_period
    normalized=[atr/bars[cfg.atr_period].close]
    for index,value in enumerate(tr[cfg.atr_period:],cfg.atr_period+1):
        atr=(atr*(cfg.atr_period-1)+value)/cfg.atr_period; normalized.append(atr/bars[index].close)
    reference=sorted(normalized[-21:-1]); current=normalized[-1]
    lo=reference[3]; hi=reference[15]  # nearest-rank 20th and 80th percentiles of 20 prior values
    evidence=evaluate(bars,cfg)
    trend='UPTREND' if evidence['reference']>evidence['sma']>evidence['prior_sma'] else 'DOWNTREND' if evidence['reference']<evidence['sma']<evidence['prior_sma'] else 'RANGE'
    label='HIGH_VOLATILITY' if current>hi else 'LOW_VOLATILITY' if current<lo else trend
    return dict(version='regime-v1',label=label,trend=trend,atr_fraction=current,lower=lo,upper=hi,
                reference_count=len(reference),reason='Relative to prior 20 ATR/close observations; descriptive, not a forecast')

def research_packet(bars,cfg,evidence,items=()):
    current=bars[-1]; condition=regime(bars,cfg)
    bull=[]; bear=[]
    for field,label in [('trend','Close and rising SMA support the trend rule'),('breakout','Close exceeds the prior breakout window'),('volume','Volume exceeds the required baseline')]:
        if evidence.get(field): bull.append({'claim':label,'evidence_ref':'rules.'+field})
        else: bear.append({'claim':label+' — not satisfied','evidence_ref':'rules.'+field})
    bear.extend([{'claim':'A gap may lose more than the planned stop','evidence_ref':'execution.gap_policy'},
                 {'claim':'Fixed intraday volume comparison ignores time-of-day effects','evidence_ref':'rules.volume_mean'}])
    if condition['label']=='UNKNOWN': bear.append({'claim':'Insufficient history to classify market conditions','evidence_ref':'regime.reason'})
    elif condition['label']=='HIGH_VOLATILITY': bear.append({'claim':'Relative volatility is above its prior 80th percentile','evidence_ref':'regime.atr_fraction'})
    coverage={k:sum(x['kind']==k for x in items) for k in ['news','fundamentals']}
    gaps=[name+' unavailable; no assessment invented' for name,n in coverage.items() if not n]
    gate=cfg.regime_policy=='observe' or condition['label'] not in ['UNKNOWN','HIGH_VOLATILITY']
    result=dict(version=VERSION,asof=current.time,method='Code-computed research lenses; NOT independent LLM agents',
        regime=condition,bull_case=bull,bear_case=bear,
        risk_review={'policy':cfg.regime_policy,'entry_policy_passed':gate,'authority':'Engine recalculates quantity, affordability and limits; human approval required'},
        coverage=coverage,missing_evidence=gaps,sources=list(items),
        conclusion='Experimental regime filter blocks entry' if not gate else 'Research does not authorize a trade')
    result['identity']=identity(result)
    return result
