"""Standalone forward polling; Streamlit does not own scheduling."""
import json,time,signal,uuid
from datetime import timedelta
from .domain import stamp,IST
from .engine import now,event
from .data import valid_session
from .ai import Reviewer

class Worker:
    def __init__(self,engine,provider,run,instruments,verification):
        self.engine=engine; self.db=engine.db; self.provider=provider; self.run=run; self.instruments=instruments
        self.verification=verification; self.stop=False
        if engine.run(run)['mode']!='FORWARD': raise ValueError('Worker requires an isolated FORWARD run')
        required=['data_rights_confirmed','unadjusted_verified','calendar_verified','no_corporate_actions','smoke_received_timestamp']
        if not all(verification.get(k) for k in required): raise ValueError('Forward blocked: verify data rights, adjustment, calendar, corporate actions and received data')
        delay=verification.get('measured_delay_seconds')
        if not isinstance(delay,(int,float)) or not 0<=delay<=60: raise ValueError('Feed delay unsupported; use replay')
        age=stamp(now())-stamp(verification['smoke_received_timestamp'])
        if not timedelta(0)<=age<=timedelta(days=1): raise ValueError('Repeat data smoke test today; future timestamps are invalid')
    def _renew(self,owner):
        t=now()
        with self.db.transaction() as c:
            updated=c.execute('UPDATE worker SET lease_until=? WHERE run=? AND lease_owner=? AND lease_until>?',
                ((stamp(t)+timedelta(minutes=5)).isoformat(),self.run,owner,t)).rowcount
            if not updated: raise RuntimeError('Worker lease lost; this worker must stop writing')
    def once(self,at=None):
        at=at or now(); r=self.engine.run(self.run); schedule=json.loads(r['schedule']); owner=uuid.uuid4().hex
        with self.db.transaction() as c:
            existing=c.execute('SELECT * FROM worker WHERE run=?',(self.run,)).fetchone()
            if existing and existing['lease_until'] and stamp(existing['lease_until'])>stamp(at): return
            c.execute('INSERT INTO worker(run,lease_until,lease_owner) VALUES(?,?,?) ON CONFLICT(run) DO UPDATE SET lease_until=excluded.lease_until,lease_owner=excluded.lease_owner',(self.run,(stamp(at)+timedelta(minutes=5)).isoformat(),owner))
        try:
            incoming=[]
            for instrument in self.instruments:
                if r['cursor'] and stamp(r['cursor']).date()<stamp(at).date():
                    incoming.extend(self.provider.historical(instrument,stamp(r['cursor']).date().isoformat(),stamp(at).date().isoformat()))
                incoming.extend(self.provider.completed(instrument,None,at))
                self._renew(owner)
            received=now()
            self._renew(owner)
            with self.db.transaction() as c:
                for b in incoming:
                    if not valid_session(b,schedule): raise ValueError('Observation outside verified calendar')
                    old=c.execute('SELECT payload FROM candles WHERE run=? AND instrument=? AND time=?',(self.run,b.instrument,b.time)).fetchone()
                    if old and old[0]!=b.model_dump_json():
                        event(c,self.run,at,'CORRECTION','Provider changed prior snapshot; original preserved; entries paused')
                        c.execute('UPDATE runs SET paused=1 WHERE id=?',(self.run,)); continue
                    c.execute('INSERT OR IGNORE INTO candles VALUES(?,?,?,?,?)',(self.run,b.instrument,b.time,b.model_dump_json(),received))
                c.execute('UPDATE worker SET last_fetch=?,error=NULL WHERE run=?',(received,self.run))
            # Catch up marks/exits, never retroactively create candidates for a missed boundary.
            while True:
                cursor=self.engine.run(self.run)['cursor']
                rows=self.db.rows('SELECT MIN(time) t FROM candles WHERE run=? AND time>COALESCE(?,\'\')',(self.run,cursor))
                t=rows[0]['t']
                if not t: break
                self._renew(owner)
                fresh=0<=(stamp(now())-stamp(t)).total_seconds()<=60
                if not fresh:
                    with self.db.transaction() as c:
                        c.execute("UPDATE orders SET state='CANCELLED',reserve=0,risk=0,reason='Offline: no retroactive forward fill' WHERE candidate IN (SELECT id FROM candidates WHERE run=?) AND state='PENDING_FILL'",(self.run,))
                        c.execute("UPDATE candidates SET state='CANCELLED',reason='Offline: no retroactive forward fill' WHERE run=? AND state='APPROVED'",(self.run,))
                if not self.engine.advance(self.run,allow_candidates=fresh): break
                if fresh: Reviewer(self.engine).review_pending(self.run)
                else:
                    with self.db.transaction() as c: event(c,self.run,at,'SKIPPED_OFFLINE',t)
            cursor=self.engine.run(self.run)['cursor']
            session=schedule.get(stamp(at).date().isoformat())
            if session and stamp(at)>=stamp(session['close']):
                for p in self.db.rows('SELECT id FROM positions WHERE run=? AND closed IS NULL',(self.run,)): self.engine.request_exit(p['id'],at)
            with self.db.transaction() as c:
                c.execute('UPDATE worker SET last_processed=?,next_check=?,lease_until=NULL,lease_owner=NULL WHERE run=? AND lease_owner=?',(cursor,(stamp(now())+timedelta(seconds=60)).isoformat(),self.run,owner))
        except Exception as exc:
            with self.db.transaction() as c:
                owned=c.execute('UPDATE worker SET error=?,lease_until=NULL,lease_owner=NULL WHERE run=? AND lease_owner=?',(type(exc).__name__+': fetch failed; check token, network and calendar',self.run,owner)).rowcount
                if owned:
                    c.execute('UPDATE runs SET paused=1 WHERE id=?',(self.run,))
                    event(c,self.run,now(),'FETCH_FAILED',type(exc).__name__)
            raise
    def serve(self):
        def stop(*_): self.stop=True
        signal.signal(signal.SIGINT,stop); signal.signal(signal.SIGTERM,stop)
        while not self.stop:
            try: self.once()
            except Exception: pass
            for _ in range(60):
                if self.stop: break
                time.sleep(1)
        with self.db.transaction() as c: event(c,self.run,now(),'SHUTDOWN','Positions remain durable; no fabricated exit')
