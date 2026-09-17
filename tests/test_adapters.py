import json
from types import SimpleNamespace
from datetime import timedelta
import pytest,httpx
from src.provider import Upstox,DataUnavailable
from src.ai import Reviewer,Review
from src.engine import Engine,now
from src.db import Database
from src.domain import Settings,stamp
from src.data import sample,sample_schedule
from src.worker import Worker

INSTRUMENT={'instrument_key':'NSE_EQ|TEST','trading_symbol':'TEST','tick_size':5}
def test_provider_normalizes_completed_only():
    def handle(request):
        assert request.method=='GET'; assert 'historical-candle' in request.url.path
        return httpx.Response(200,json={'status':'success','data':{'candles':[['2026-09-15T09:15:00+05:30',100,102,99,101,1000,0],['2026-09-15T09:30:00+05:30',101,102,99,101,1000,0]]}})
    p=Upstox('fake',httpx.Client(transport=httpx.MockTransport(handle)))
    bars=p.completed(INSTRUMENT,None,'2026-09-15T09:35:00+05:30')
    assert len(bars)==1; assert bars[0].time=='2026-09-15T09:30:00+05:30'; assert bars[0].close==10100

def test_provider_auth_and_missing():
    with pytest.raises(DataUnavailable): Upstox('').historical(INSTRUMENT,'2026-09-14','2026-09-15')
    p=Upstox('secret',httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(401))))
    with pytest.raises(DataUnavailable,match='Authentication'): p.historical(INSTRUMENT,'2026-09-14','2026-09-15')

def test_provider_bounded_retries(monkeypatch):
    monkeypatch.setattr('src.provider.time.sleep',lambda _:None)
    calls=[]
    def fail(request): calls.append(request); return httpx.Response(429)
    p=Upstox('private',httpx.Client(transport=httpx.MockTransport(fail)))
    with pytest.raises(DataUnavailable): p.historical(INSTRUMENT,'2026-09-14','2026-09-15')
    assert len(calls)==3

def setup_ai(tmp_path,monkeypatch):
    e=Engine(Database(tmp_path/'ai.db')); run=e.create(sample(),sample_schedule(),Settings(ai_mode='openai'),'SAMPLE')
    for _ in range(28):e.advance(run)
    # Mock a current forward snapshot; no actual HTTP call is made.
    with e.db.transaction() as c: c.execute("UPDATE runs SET mode='FORWARD' WHERE id=?",(run,))
    p=e.db.rows('SELECT * FROM candidates ORDER BY instrument')[0]
    monkeypatch.setattr('src.ai.now',lambda:p['time'])
    monkeypatch.setenv('AI_BUDGET_APPROVED','true'); monkeypatch.setenv('AI_DAILY_USD','0.03'); monkeypatch.setenv('AI_DAILY_REQUESTS','1'); monkeypatch.setenv('OPENAI_MODEL','gpt-5-mini')
    return e,run,p

@pytest.mark.parametrize('kind',['valid','wrong','refusal','timeout','malformed'])
def test_sdk_response_handling(tmp_path,monkeypatch,kind):
    e,run,p=setup_ai(tmp_path,monkeypatch); calls=[]
    def parse(**kwargs):
        calls.append(kwargs); assert kwargs['store'] is False; assert 'tools' not in kwargs; assert 'temperature' not in kwargs
        if kind=='timeout': raise TimeoutError('secret token must not leak')
        if kind=='malformed': raise ValueError('bad schema with secret')
        output=None if kind=='refusal' else Review(candidate_id='other' if kind=='wrong' else p['id'],decision='PAPER_TRADE',supporting_factors=[],risk_factors=['Test'],summary='Mock SDK response')
        return SimpleNamespace(status='completed',output_parsed=output,usage=None)
    client=SimpleNamespace(responses=SimpleNamespace(parse=parse))
    result=Reviewer(e,client).review(p['id'])
    assert result['status']==('VALID' if kind=='valid' else 'FAILED')
    Reviewer(e,client).review(p['id']); assert len(calls)==1
    assert 'secret' not in (result['error'] or '')
    second=e.db.rows('SELECT * FROM candidates WHERE id<>?',(p['id'],))[0]
    result=Reviewer(e,client).review(second['id']); assert result['error']=='BUDGET_EXHAUSTED'; assert len(calls)==1

def test_worker_blocks_unverified(tmp_path):
    e=Engine(Database(tmp_path/'w.db')); run=e.create(sample(),sample_schedule(),mode='FORWARD')
    with pytest.raises(ValueError,match='Forward blocked'): Worker(e,None,run,[],{})

@pytest.mark.parametrize('invalid_budget',['NaN','Infinity','-1'])
def test_invalid_budget_cannot_allow_paid_request(tmp_path,monkeypatch,invalid_budget):
    e,run,p=setup_ai(tmp_path,monkeypatch)
    monkeypatch.setenv('AI_DAILY_USD',invalid_budget)
    class NoCalls:
        def parse(self,**kwargs): raise AssertionError('No paid call permitted')
    result=Reviewer(e,SimpleNamespace(responses=NoCalls())).review(p['id'])
    assert result['error']=='BUDGET_EXHAUSTED' and result['allowance']==0
