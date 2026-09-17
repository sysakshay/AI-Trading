"""Read-only Upstox V3 adapter: only GET metadata and candle endpoints exist."""
import gzip,json,time
from datetime import timedelta
from typing import Protocol
from urllib.parse import quote
import httpx
from .domain import Candle,stamp,money
from .engine import now

class DataUnavailable(RuntimeError): pass
class Provider(Protocol):
    def instruments(self): ...
    def historical(self,instrument,start,end): ...
    def completed(self,instrument,after,asof): ...

class Upstox:
    metadata={'provider':'Upstox V3','delay':'UNVERIFIED','adjustment':'unverified; exclude corporate-action intervals','timestamp':'provider bar start converted to end','connected':False}
    def __init__(self,token,client=None):
        self.token=token; self.client=client or httpx.Client(timeout=20,follow_redirects=False); self.last=0
    def _get(self,url,auth=True):
        if auth and not self.token: raise DataUnavailable('Missing UPSTOX_ACCESS_TOKEN; enter privately in .env')
        for attempt in range(3):
            time.sleep(max(0,1.0-(time.monotonic()-self.last)))
            self.last=time.monotonic()
            try:
                r=self.client.get(url,headers={'Authorization':'Bearer '+self.token,'Accept':'application/json'} if auth else {})
                if r.status_code in [401,403]: raise DataUnavailable('Authentication/entitlement denied; renew token or confirm access')
                if r.status_code==429 or r.status_code>=500:
                    if attempt<2: time.sleep(2**attempt); continue
                if r.status_code!=200: raise DataUnavailable('Provider HTTP '+str(r.status_code))
                return r
            except (httpx.TimeoutException,httpx.NetworkError):
                if attempt==2: raise DataUnavailable('Network unavailable after 3 attempts') from None
        raise DataUnavailable('Provider retry limit reached')
    def instruments(self):
        r=self._get('https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz',False)
        content=r.content
        if content[:2]==b'\x1f\x8b': content=gzip.decompress(content)
        data=json.loads(content)
        return [x for x in data if x.get('segment')=='NSE_EQ' and x.get('instrument_type')=='EQ']
    def lookup(self,symbol):
        matches=[x for x in self.instruments() if x.get('trading_symbol')==symbol]
        if len(matches)!=1: raise DataUnavailable('No unique NSE cash equity for symbol')
        return matches[0]
    def _bars(self,instrument,path,asof=None):
        data=self._get('https://api.upstox.com'+path).json()
        if data.get('status')!='success': raise DataUnavailable('Provider did not return success')
        rows=[]
        for x in data['data']['candles']:
            end=stamp(x[0])+timedelta(minutes=15)
            if asof and end>stamp(asof): continue
            rows.append(Candle(instrument=instrument['instrument_key'],symbol=instrument['trading_symbol'],end=end,
                open=money(x[1]),high=money(x[2]),low=money(x[3]),close=money(x[4]),volume=x[5],source='UPSTOX',
                tick_paise=int(instrument['tick_size']))) # instrument JSON tick_size is paise, verify against metadata.
        rows.sort(key=lambda b:b.end)
        if len({b.time for b in rows})!=len(rows): raise DataUnavailable('Conflicting or duplicate provider candles')
        return rows
    def historical(self,instrument,start,end):
        from datetime import date
        if (date.fromisoformat(end)-date.fromisoformat(start)).days>28: raise DataUnavailable('Request chunks of at most 28 days')
        key=quote(instrument['instrument_key'],safe='')
        return self._bars(instrument,f'/v3/historical-candle/{key}/minutes/15/{end}/{start}',now())
    def completed(self,instrument,after,asof):
        key=quote(instrument['instrument_key'],safe='')
        return [b for b in self._bars(instrument,f'/v3/historical-candle/intraday/{key}/minutes/15',asof) if not after or b.time>after]
