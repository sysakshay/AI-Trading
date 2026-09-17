import json
from collections import defaultdict
from .domain import stamp

def report(db,run,start=None,end=None):
    start=stamp(start).isoformat() if start else None
    end=stamp(end).isoformat() if end else None
    if start and end and start>=end: raise ValueError('Report start must precede exclusive end')
    def in_period(t): return (not start or t>=start) and (not end or t<end)
    r=db.rows('SELECT * FROM runs WHERE id=?',(run,))[0]
    sources=[x['source'] for x in db.rows("SELECT DISTINCT json_extract(payload,'$.source') source FROM candles WHERE run=?",(run,))]
    all_positions=db.rows('SELECT * FROM positions WHERE run=? ORDER BY closed,id',(run,))
    positions=[p for p in all_positions if p['closed'] and in_period(p['closed'])]
    pnl=[(p['exit']-p['entry'])*p['qty']-p['entry_fee']-p['exit_fee'] for p in positions]
    wins=[x for x in pnl if x>0]; losses=[x for x in pnl if x<0]
    full_curve=db.rows('SELECT * FROM equity WHERE run=? ORDER BY time',(run,))
    before=[p for p in full_curve if start and p['time']<start]
    opening_equity=before[-1]['value'] if before else r['initial']
    curve=[p for p in full_curve if in_period(p['time'])]
    peak=opening_equity; dd=0; dd_pct=0; longest=0; streak=0
    for point in curve:
        peak=max(peak,point['value']); point['drawdown']=point['value']-peak
        dd=max(dd,peak-point['value'])
        dd_pct=max(dd_pct,(peak-point['value'])/peak if peak else 0)
    for x in pnl:
        streak=streak+1 if x<0 else 0; longest=max(longest,streak)
    open_positions=[dict(p) for p in all_positions if (not end or p['opened']<end) and (not p['closed'] or (end and p['closed']>=end))]
    latest=[p for p in full_curve if not end or p['time']<end]
    asof=latest[-1]['time'] if latest else None
    for p in open_positions:
        marks=db.rows('SELECT payload,time FROM candles WHERE run=? AND instrument=? AND time<=? ORDER BY time DESC LIMIT 1',(run,p['instrument'],asof or ''))
        p['mark']=json.loads(marks[0]['payload'])['close'] if marks else p['entry']
        p['marked']=marks[0]['time'] if marks else None
    fills=db.rows('SELECT * FROM fills WHERE run=?',(run,))
    costs=sum(f['fee'] for f in fills if in_period(f['time']))
    ledger=db.rows("SELECT amount,time FROM ledger WHERE run=? AND kind<>'INITIAL'",(run,))
    cash=r['initial']+sum(x['amount'] for x in ledger if not end or x['time']<end)
    expenses=db.rows('SELECT * FROM operating_expenses WHERE run=? ORDER BY time,id',(run,))
    expenses=[x for x in expenses if in_period(x['time'])]
    events=db.rows('SELECT kind,time FROM events WHERE run=?',(run,)); counts=defaultdict(int)
    for x in events:
        if in_period(x['time']): counts[x['kind']]+=1
    events=[{'kind':k,'n':v} for k,v in sorted(counts.items())]
    candidates=db.rows('SELECT * FROM candidates WHERE run=?',(run,)); by_id={p['id']:p for p in candidates}
    regimes=defaultdict(list)
    for p,value in zip(positions,pnl):
        research=json.loads(by_id[p['candidate']]['evidence']).get('research',{})
        regimes[research.get('regime',{}).get('label','LEGACY_UNKNOWN')].append(value)
    states=defaultdict(int)
    for p in candidates:
        if in_period(p['time']): states[p['state']]+=1
    equity_end=latest[-1]['value'] if latest else r['initial']
    period_points=curve if start or end else full_curve
    return dict(mode=r['mode'],data_sources=sources,contains_synthetic='SYNTHETIC' in sources,strategy=r['strategy'],data_hash=r['data_hash'],period=[start,end],completed_trades=len(pnl),
        net_realized_paise=sum(pnl),gross_closed_paise=sum((p['exit']-p['entry'])*p['qty'] for p in positions),
        transaction_costs_paise=costs,win_rate=len(wins)/len(pnl) if pnl else None,
        average_win_paise=sum(wins)/len(wins) if wins else None,average_loss_paise=sum(losses)/len(losses) if losses else None,
        expectancy_paise=sum(pnl)/len(pnl) if pnl else None,profit_factor=sum(wins)/abs(sum(losses)) if losses else None,
        max_drawdown_paise=dd,max_drawdown_fraction=dd_pct,longest_losing_sequence=longest,cash_paise=cash,
        opening_equity_paise=opening_equity,ending_equity_paise=equity_end,
        equity_change_paise=equity_end-opening_equity,valuation_asof=asof,
        closed_trade_costs_paise=sum(p['entry_fee']+p['exit_fee'] for p in positions),
        open_positions=len(open_positions),unrealized_paise=sum((p['mark']-p['entry'])*p['qty']-p['entry_fee'] for p in open_positions),
        valuation_uncertain=bool(latest and latest[-1]['uncertain']) or any(p['marked']!=asof for p in open_positions),equity_curve=curve,
        exposure_bar_fraction=sum(any(p['opened']<=x['time'] and (not p['closed'] or p['closed']>x['time']) for p in all_positions) for x in period_points)/len(period_points) if period_points else None,
        candidate_states=[{'state':k,'count':v} for k,v in sorted(states.items())],
        regime_breakdown=[{'regime':k,'trades':len(v),'net_paise':sum(v),'expectancy_paise':sum(v)/len(v)} for k,v in sorted(regimes.items())],
        sample_assessment='INSUFFICIENT: fewer than 30 closed trades' if len(pnl)<30 else 'Review sample diversity and independence; count alone establishes no edge',
        operational_counts=events,
        ai_reserved_usd=sum(x['allowance'] for x in db.rows('SELECT allowance FROM reviews a JOIN candidates c ON c.id=a.candidate WHERE c.run=?',(run,))),
        operating_expenses=expenses,operating_costs_paise=sum(x['amount'] for x in expenses),
        economic_realized_paise=sum(pnl)-sum(x['amount'] for x in expenses),
        operating_costs='User-recorded INR allocations; no invoice/provider credit is inferred. AI USD reservations are separate.',
        limitations=['Synthetic results are not evidence of profitability' if 'SYNTHETIC' in sources else 'Sample sufficiency not established',
                      'Period is [start,end); drawdown and exposure use selected bar-close observations','Open marks exclude future exit charges','Closed-trade P&L attributes both fees at exit; transaction costs show fees paid in period',
                      'Candidate states are current lifecycle states, grouped by creation period','No losses: profit factor undefined, not infinite success'])

def export_run(db,run):
    tables={}
    for table in ['runs','candles','sessions','candidates','positions','fills','ledger','events','equity','worker','research_items','operating_expenses']:
        tables[table]=db.rows(f'SELECT * FROM {table} WHERE '+('id' if table=='runs' else 'run')+'=?',(run,))
    for table in ['reviews','orders','decisions']:
        tables[table]=db.rows(f'SELECT t.* FROM {table} t JOIN candidates c ON c.id=t.candidate WHERE c.run=?',(run,))
    return json.dumps(tables,indent=2)

def add_expense(db,run,category,amount_paise,note='',key=None):
    from .engine import uid,now
    if category not in ['AI','DATA','OTHER'] or type(amount_paise) is not int or amount_paise<0: raise ValueError('Invalid expense')
    if len(note)>200: raise ValueError('Note must be at most 200 characters')
    key=key or uid()
    with db.transaction() as c:
        r=c.execute('SELECT * FROM runs WHERE id=?',(run,)).fetchone()
        if not r: raise ValueError('Unknown run')
        t=r['cursor'] or now()
        c.execute('INSERT OR IGNORE INTO operating_expenses VALUES(?,?,?,?,?,?)',(key,run,t,category,amount_paise,note))
    return key
