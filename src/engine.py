from __future__ import annotations
import json, uuid
from datetime import datetime,timedelta
from .domain import Settings,Candle,stamp,evaluate,size,fee,slipped,identity,IST
from .data import valid_session
from .research import known_items,research_packet

def uid(): return uuid.uuid4().hex
def now(): return datetime.now(IST).isoformat()
def event(c,run,t,kind,detail): c.execute('INSERT INTO events(run,time,kind,detail) VALUES(?,?,?,?)',(run,t,kind,detail))

class Engine:
    def __init__(self,db): self.db=db
    def create(self,bars,schedule,cfg=None,mode='SAMPLE'):
        if mode not in ['SAMPLE','REPLAY','BACKTEST','FORWARD']: raise ValueError('Unsupported mode')
        cfg=cfg or Settings(); bars=list(bars)
        if not bars: raise ValueError('No candles')
        seen=set(); previous={}
        for b in bars:
            if not valid_session(b,schedule): raise ValueError('Candle outside explicit session schedule: '+b.time)
            if (b.instrument,b.time) in seen: raise ValueError('Duplicate candle')
            if b.instrument in previous and b.end<=previous[b.instrument]: raise ValueError('Out-of-order candle')
            seen.add((b.instrument,b.time)); previous[b.instrument]=b.end
        run=uid()
        with self.db.transaction() as c:
            c.execute('INSERT INTO runs(id,mode,config,strategy,data_hash,schedule,cash,initial,created,code_version) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (run,mode,cfg.model_dump_json(),cfg.version,identity([b.model_dump(mode='json') for b in bars]),json.dumps(schedule),cfg.initial_paise,cfg.initial_paise,now(),'0.2.0'))
            c.execute('INSERT INTO ledger VALUES(?,?,?,?,?,?)',(uid(),run,None,cfg.initial_paise,now(),'INITIAL'))
            for b in bars:
                c.execute('INSERT OR IGNORE INTO instruments(id,symbol,exchange,tick) VALUES(?,?,?,?)',(b.instrument,b.symbol,'SYNTHETIC' if b.source=='SYNTHETIC' else 'NSE',b.tick_paise))
                c.execute('INSERT INTO candles VALUES(?,?,?,?,?)',(run,b.instrument,b.time,b.model_dump_json(),now()))
            event(c,run,now(),'CREATED',mode+'; immutable inputs; '+cfg.version)
        return run
    def run(self,run): return self.db.rows('SELECT * FROM runs WHERE id=?',(run,))[0]
    def bars(self,run,instrument=None,upto=None):
        sql='SELECT payload FROM candles WHERE run=?'; args=[run]
        if instrument: sql+=' AND instrument=?'; args.append(instrument)
        if upto: sql+=' AND time<=?'; args.append(upto)
        return [Candle.model_validate_json(r['payload']) for r in self.db.rows(sql+' ORDER BY time,instrument',args)]
    def account(self,c,run,t):
        r=c.execute('SELECT * FROM runs WHERE id=?',(run,)).fetchone()
        positions=c.execute('SELECT * FROM positions WHERE run=? AND closed IS NULL',(run,)).fetchall()
        orders=c.execute("SELECT o.* FROM orders o JOIN candidates p ON p.id=o.candidate WHERE p.run=? AND o.state='PENDING_FILL'",(run,)).fetchall()
        return dict(cash=r['cash'],equity=r['cash']+sum(p['qty']*p['mark'] for p in positions),
            reserved=sum(o['reserve'] for o in orders),risk=sum(p['risk'] for p in positions)+sum(o['risk'] for o in orders),
            count=len(positions)+len(orders),stale=any(p['marked']!=t for p in positions),positions=[dict(p) for p in positions])
    def _eligible(self,c,r,candidate,bar,t,exclude_order=False):
        cfg=Settings.model_validate_json(r['config']); a=self.account(c,r['id'],t)
        session=c.execute('SELECT * FROM sessions WHERE run=? AND day=?',(r['id'],stamp(t).date().isoformat())).fetchone()
        schedule=json.loads(r['schedule']); close=stamp(schedule[stamp(t).date().isoformat()]['close'])
        if r['paused']: return 0,'Entries paused'
        if stamp(t)>=close-timedelta(minutes=30): return 0,'Last-entry cutoff'
        if session and (session['halted'] or session['trades']>=cfg.max_trades): return 0,'Daily loss halt or daily trade limit'
        if a['stale']: return 0,'Stale position marks; valuation uncertain'
        if a['count']>=cfg.max_positions: return 0,'Maximum positions including pending orders'
        exists=c.execute('SELECT 1 FROM positions WHERE run=? AND instrument=? AND closed IS NULL',(r['id'],bar.instrument)).fetchone()
        if exists: return 0,'Instrument already open'
        entry=slipped(bar.close,cfg,True,bar.tick_paise)
        if not candidate['stop']<entry<candidate['target']: return 0,'Original stop/target crossed'
        conservative_stop=slipped(candidate['stop'],cfg,False,bar.tick_paise)
        conservative_target=slipped(candidate['target'],cfg,False,bar.tick_paise)
        return size(entry,conservative_stop,conservative_target,bar.volume,a['cash']-a['reserved'],a['equity'],a['risk'],cfg)
    def decide(self,candidate_id,revision,approve=True,actor='human',at=None):
        with self.db.transaction() as c:
            p=c.execute('SELECT * FROM candidates WHERE id=?',(candidate_id,)).fetchone()
            if not p: raise ValueError('Unknown candidate')
            r=c.execute('SELECT * FROM runs WHERE id=?',(p['run'],)).fetchone(); t=at or (now() if r['mode']=='FORWARD' else r['cursor'])
            if p['revision']!=revision: raise ValueError('Proposal revision changed')
            if p['state']!='AWAITING_APPROVAL': return False,'Already decided or unavailable'
            if stamp(t)<stamp(p['time']): raise ValueError('Decision precedes signal')
            if stamp(t)>=stamp(p['expiry']):
                c.execute("UPDATE candidates SET state='EXPIRED',reason='Approval expired' WHERE id=?",(p['id'],)); return False,'Expired'
            if r['mode']=='FORWARD' and (stamp(t)-stamp(r['cursor'])).total_seconds()>60: return False,'Forward feed stale; wait for current data'
            if not approve:
                c.execute("UPDATE candidates SET state='REJECTED',reason='User/policy rejection' WHERE id=?",(p['id'],))
                c.execute('INSERT INTO decisions(candidate,revision,action,actor,time) VALUES(?,?,?,?,?)',(p['id'],revision,'REJECT',actor,t)); return True,'Rejected'
            cfg=Settings.model_validate_json(r['config'])
            if cfg.ai_mode!='rules':
                review=c.execute("SELECT * FROM reviews WHERE candidate=? AND status='VALID' ORDER BY completed DESC LIMIT 1",(p['id'],)).fetchone()
                if not review or json.loads(review['response'])['decision']!='PAPER_TRADE': return False,'AI review unavailable or filtered; entry blocked'
                if stamp(review['completed'])>stamp(t): return False,'Review not yet available'
            bar=Candle.model_validate_json(c.execute('SELECT payload FROM candles WHERE run=? AND instrument=? AND time<=? ORDER BY time DESC LIMIT 1',(p['run'],p['instrument'],t)).fetchone()[0])
            if (stamp(t)-bar.end).total_seconds()>900: return False,'Stale data'
            qty,reason=self._eligible(c,r,p,bar,r['cursor'])
            if not qty: return False,reason
            entry=slipped(bar.close,cfg,True,bar.tick_paise); cost=entry*qty+fee(entry,qty,cfg)
            risk=(entry-slipped(p['stop'],cfg,False,bar.tick_paise))*qty+fee(entry,qty,cfg)+fee(p['stop'],qty,cfg)
            c.execute('INSERT INTO decisions(candidate,revision,action,actor,time) VALUES(?,?,?,?,?)',(p['id'],revision,'APPROVE',actor,t))
            c.execute("INSERT INTO orders VALUES(?,?,'PENDING_FILL',?,?,?,?,'')",(uid(),p['id'],t,qty,cost,risk))
            c.execute("UPDATE candidates SET state='APPROVED' WHERE id=?",(p['id'],))
            event(c,p['run'],t,'APPROVED',p['id'])
            return True,'Approved; reserved cash; waiting for a later completed close'
    def pause(self,run,paused):
        with self.db.transaction() as c:
            c.execute('UPDATE runs SET paused=? WHERE id=?',(int(paused),run)); event(c,run,now(),'PAUSE',str(paused))
    def request_exit(self,position,at=None):
        with self.db.transaction() as c:
            p=c.execute('SELECT p.*,r.cursor,r.mode FROM positions p JOIN runs r ON r.id=p.run WHERE p.id=?',(position,)).fetchone()
            if p and not p['closed']:
                t=at or (now() if p['mode']=='FORWARD' else p['cursor'])
                c.execute('UPDATE positions SET exit_requested=COALESCE(exit_requested,?) WHERE id=?',(t,position))
                event(c,p['run'],t,'EXIT_REQUESTED',position)
    def _close(self,c,p,bar,t,cfg,price,reason):
        price=slipped(price,cfg,False,bar.tick_paise); charges=fee(price,p['qty'],cfg); fill=uid()
        c.execute('UPDATE positions SET closed=?,exit=?,exit_fee=?,reason=?,mark=?,marked=? WHERE id=?',(t,price,charges,reason,price,t,p['id']))
        c.execute('INSERT INTO fills VALUES(?,?,?,?,?,?,?,?)',(fill,p['run'],p['id'],'SELL',p['qty'],price,charges,t))
        amount=price*p['qty']-charges
        c.execute('UPDATE runs SET cash=cash+? WHERE id=?',(amount,p['run']))
        c.execute('INSERT INTO ledger VALUES(?,?,?,?,?,?)',(uid(),p['run'],fill,amount,t,reason)); event(c,p['run'],t,'EXIT',reason)
    def advance(self,run,allow_candidates=True):
        with self.db.transaction() as c:
            r=c.execute('SELECT * FROM runs WHERE id=?',(run,)).fetchone(); cfg=Settings.model_validate_json(r['config'])
            next_row=c.execute('SELECT MIN(time) FROM candles WHERE run=? AND time>COALESCE(?,\'\')',(run,r['cursor'])).fetchone()
            t=next_row[0]
            if not t: return None
            if r['mode']=='FORWARD' and stamp(t)>stamp(now()): return None
            day=stamp(t).date().isoformat(); schedule=json.loads(r['schedule']); close=stamp(schedule[day]['close'])
            a=self.account(c,run,r['cursor'])
            c.execute('INSERT OR IGNORE INTO sessions VALUES(?,?,?,0,0)',(run,day,a['equity']))
            bars=[Candle.model_validate_json(x[0]) for x in c.execute('SELECT payload FROM candles WHERE run=? AND time=? ORDER BY instrument',(run,t))]
            by_id={b.instrument:b for b in bars}
            # Exits/marks always run, independently of pause and AI.
            for p in c.execute('SELECT * FROM positions WHERE run=? AND closed IS NULL',(run,)).fetchall():
                b=by_id.get(p['instrument'])
                if not b:
                    event(c,run,t,'STALE','Missing position observation; unresolved exit if session ended'); continue
                c.execute('UPDATE positions SET mark=?,marked=? WHERE id=?',(b.close,t,p['id']))
                reason=None; price=None
                prior_day=stamp(p['opened']).date()<stamp(t).date()
                if prior_day: price=b.open; reason='UNRESOLVED_SESSION_EXIT'
                elif b.low<=p['stop']: price=min(b.open,p['stop']); reason='STOP (stop-first)'
                elif b.high>=p['target']: price=p['target']; reason='TARGET (limit; no favorable gap improvement)'
                elif p['exit_requested'] and stamp(t)>stamp(p['exit_requested']): price=b.close; reason='MANUAL'
                elif stamp(t)>=close: price=b.close; reason='SESSION_CLOSE'
                if reason: self._close(c,p,b,t,cfg,price,reason)
            a=self.account(c,run,t); session=c.execute('SELECT * FROM sessions WHERE run=? AND day=?',(run,day)).fetchone()
            if a['equity']<=session['equity']*(1-cfg.daily_loss):
                c.execute('UPDATE sessions SET halted=1 WHERE run=? AND day=?',(run,day))
                event(c,run,t,'HALT','Daily loss limit latched')
            c.execute("UPDATE candidates SET state='EXPIRED',reason='Approval window ended' WHERE run=? AND state IN ('AWAITING_APPROVAL','PENDING_REVIEW') AND expiry<=?",(run,t))
            orders=c.execute("SELECT o.*,p.instrument,p.stop,p.target,p.run,p.time signal_time FROM orders o JOIN candidates p ON p.id=o.candidate WHERE p.run=? AND o.state='PENDING_FILL'",(run,)).fetchall()
            for o in orders:
                if stamp(t)<=stamp(o['approved']): continue
                b=by_id.get(o['instrument'])
                c.execute("UPDATE orders SET state='CHECKING',reserve=0,risk=0 WHERE id=?",(o['id'],))
                r=c.execute('SELECT * FROM runs WHERE id=?',(run,)).fetchone()
                if b and stamp(t)-stamp(o['approved'])<=timedelta(minutes=15) and stamp(t).date()==stamp(o['approved']).date():
                    qty,reason=self._eligible(c,r,o,b,t)
                    qty=min(qty,o['qty'])
                else: qty,reason=0,'Missing next observation or approval too old'
                if qty:
                    entry=slipped(b.close,cfg,True,b.tick_paise); charges=fee(entry,qty,cfg); pos=uid(); fill=uid()
                    risk=(entry-slipped(o['stop'],cfg,False,b.tick_paise))*qty+charges+fee(o['stop'],qty,cfg)
                    c.execute('INSERT INTO positions(id,run,instrument,candidate,qty,entry,entry_fee,stop,target,risk,opened,mark,marked) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (pos,run,b.instrument,o['candidate'],qty,entry,charges,o['stop'],o['target'],risk,t,b.close,t))
                    c.execute('INSERT INTO fills VALUES(?,?,?,?,?,?,?,?)',(fill,run,pos,'BUY',qty,entry,charges,t))
                    amount=-(entry*qty+charges)
                    c.execute('UPDATE runs SET cash=cash+? WHERE id=?',(amount,run))
                    c.execute('INSERT INTO ledger VALUES(?,?,?,?,?,?)',(uid(),run,fill,amount,t,'ENTRY'))
                    c.execute('UPDATE sessions SET trades=trades+1 WHERE run=? AND day=?',(run,day))
                c.execute('UPDATE orders SET state=?,reason=? WHERE id=?',('FILLED' if qty else 'CANCELLED',reason,o['id']))
                c.execute('UPDATE candidates SET state=?,reason=? WHERE id=?',('FILLED' if qty else 'CANCELLED',reason,o['candidate']))
            if allow_candidates and not r['paused'] and stamp(t)<close-timedelta(minutes=30):
                for b in bars:
                    history=[Candle.model_validate_json(x[0]) for x in c.execute('SELECT payload FROM candles WHERE run=? AND instrument=? AND time<=? ORDER BY time',(run,b.instrument,t))]
                    observed={x.time for x in history}
                    missing=False
                    for session_times in schedule.values():
                        expected=stamp(session_times['open'])+timedelta(minutes=15)
                        while expected<=stamp(session_times['close']) and expected<=stamp(t):
                            if expected>=history[0].end and expected.isoformat() not in observed: missing=True; break
                            expected+=timedelta(minutes=15)
                        if missing: break
                    if missing:
                        event(c,run,t,'DATA_GAP',b.instrument+' missing scheduled bar; candidate blocked'); continue
                    evidence=evaluate(history,cfg)
                    if not evidence['eligible']: continue
                    existing=c.execute("SELECT 1 FROM candidates WHERE run=? AND instrument=? AND state IN ('PENDING_REVIEW','AWAITING_APPROVAL','APPROVED')",(run,b.instrument)).fetchone()
                    opened=c.execute('SELECT 1 FROM positions WHERE run=? AND instrument=? AND closed IS NULL',(run,b.instrument)).fetchone()
                    if existing or opened: continue
                    expiry=min(stamp(t)+timedelta(minutes=15),close-timedelta(minutes=30)).isoformat()
                    evidence['research']=research_packet(history,cfg,evidence,known_items(c,run,b.instrument,t))
                    gate=evidence['research']['risk_review']['entry_policy_passed']
                    p=uid(); state=('AWAITING_APPROVAL' if cfg.ai_mode=='rules' else 'PENDING_REVIEW') if gate else 'REJECTED'
                    c.execute('INSERT OR IGNORE INTO candidates(id,run,instrument,time,expiry,state,evidence,stop,target,reason) VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (p,run,b.instrument,t,expiry,state,json.dumps(evidence),evidence['stop'],evidence['target'],'' if gate else 'Experimental regime gate: '+evidence['research']['regime']['label']))
                    event(c,run,t,'CANDIDATE',p)
            c.execute('UPDATE runs SET cursor=? WHERE id=?',(t,run))
            a=self.account(c,run,t)
            session=c.execute('SELECT * FROM sessions WHERE run=? AND day=?',(run,day)).fetchone()
            if a['equity']<=session['equity']*(1-cfg.daily_loss):
                c.execute('UPDATE sessions SET halted=1 WHERE run=? AND day=?',(run,day))
            c.execute('INSERT INTO equity VALUES(?,?,?,?)',(run,t,a['equity'],int(a['stale'])))
            event(c,run,t,'ADVANCE','Completed candles processed')
        return t
    def backtest(self,run,reviewer=None):
        while self.advance(run):
            if reviewer: reviewer.review_pending(run)
            for p in self.db.rows("SELECT * FROM candidates WHERE run=? AND state='AWAITING_APPROVAL' ORDER BY instrument",(run,)):
                ok,reason=self.decide(p['id'],p['revision'],actor='automatic-fixed-policy')
                if not ok:
                    self.decide(p['id'],p['revision'],False,actor='automatic-fixed-policy')
        return run
