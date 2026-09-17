from __future__ import annotations
import csv, io, json, hashlib
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field, model_validator

IST = ZoneInfo('Asia/Kolkata')
def stamp(t):
    if isinstance(t, str): t = datetime.fromisoformat(t)
    if t.tzinfo is None or t.utcoffset() is None: raise ValueError('Timestamp must include timezone offset')
    return t.astimezone(IST)
def money(x): return int((Decimal(str(x))*100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
def tick(x, upward=False, step=5):
    return int((Decimal(str(x))/step).to_integral_value(rounding=ROUND_CEILING if upward else ROUND_FLOOR))*step
def identity(x): return hashlib.sha256(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()

class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    initial_paise: int = Field(default=1000000, ge=10000, le=10000000000)
    risk: float = Field(default=.005, gt=0, le=.005)
    aggregate: float = Field(default=.01, gt=0, le=.01)
    daily_loss: float = Field(default=.01, gt=0, le=.01)
    max_positions: int = Field(default=2, ge=1, le=2)
    max_trades: int = Field(default=3, ge=1, le=3)
    sma: int = Field(default=20, ge=5, le=100)
    lookback: int = Field(default=20, ge=5, le=100)
    atr_period: int = Field(default=14, ge=2, le=100)
    volume_multiple: float = Field(default=1.5, ge=1, le=10)
    stop_atr: float = Field(default=1.5, ge=.5, le=5)
    target_r: float = Field(default=2, ge=1.5, le=5)
    min_net_rr: float = Field(default=1.5, ge=1, le=5)
    fee_bps: int = Field(default=10, ge=0, le=100)
    fee_fixed_paise: int = Field(default=0, ge=0, le=10000)
    slip_bps: int = Field(default=2, ge=0, le=100)
    participation: float = Field(default=.01, gt=0, le=.01)
    ai_mode: Literal['rules','mock','mock_fail','openai'] = 'mock'
    regime_policy: Literal['observe','avoid_high_volatility'] = 'observe'
    @property
    def version(self): return 'breakout-v1-' + identity(self.model_dump())[:12]

class Candle(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    instrument: str = Field(min_length=1, max_length=80, pattern=r'^[A-Za-z0-9_|.:-]+$')
    symbol: str = Field(min_length=1, max_length=60, pattern=r'^[A-Za-z0-9_.:-]+$')
    end: datetime
    open: int = Field(gt=0)
    high: int = Field(gt=0)
    low: int = Field(gt=0)
    close: int = Field(gt=0)
    volume: int = Field(ge=0)
    source: str = 'SYNTHETIC'
    interval: Literal[15] = 15
    adjustment: Literal['unadjusted'] = 'unadjusted'
    tick_paise: int = Field(default=5, gt=0)
    @model_validator(mode='after')
    def valid(self):
        stamp(self.end)
        if self.low > min(self.open,self.close) or self.high < max(self.open,self.close) or self.low > self.high:
            raise ValueError('Impossible OHLC relationship')
        return self
    @property
    def time(self): return stamp(self.end).isoformat()

def fee(price, qty, cfg):
    return int((Decimal(price*qty)*Decimal(cfg.fee_bps)/10000).to_integral_value(rounding=ROUND_CEILING)) + cfg.fee_fixed_paise
def slipped(price, cfg, buy=False, step=5):
    return tick(Decimal(price)*(1+Decimal(cfg.slip_bps)/10000 if buy else 1-Decimal(cfg.slip_bps)/10000), buy, step)

def size(entry, stop, target, volume, cash, equity, open_risk, cfg):
    if not 0 < stop < entry < target: return 0, 'Original stop/target crossed'
    budget = min(int(Decimal(equity)*Decimal(str(cfg.risk))), int(Decimal(equity)*Decimal(str(cfg.aggregate)))-open_risk)
    upper = min(cash//entry, max(0,budget)//(entry-stop), int(volume*cfg.participation))
    for qty in range(upper, 0, -1):
        loss = (entry-stop)*qty + fee(entry,qty,cfg)+fee(stop,qty,cfg)
        gain = (target-entry)*qty - fee(entry,qty,cfg)-fee(target,qty,cfg)
        if entry*qty+fee(entry,qty,cfg)<=cash and loss<=budget and gain/loss>=cfg.min_net_rr:
            return qty, 'Eligible; costs are estimates'
    return 0, 'Zero shares: risk, cash, liquidity or net reward-to-risk limit'

def evaluate(bars, cfg):
    need = max(cfg.sma+3,cfg.lookback+1,cfg.atr_period+1)
    if len(bars)<need: return {'eligible':False,'reason':f'Warm-up: {len(bars)}/{need} bars'}
    # Missing intraday bars invalidate the contiguous analytical window.
    for a,b in zip(bars,bars[1:]):
        if stamp(a.end).date()==stamp(b.end).date() and b.end-a.end!=timedelta(minutes=15):
            return {'eligible':False,'reason':'Missing or unordered bar; restart warm-up with contiguous data'}
    closes=[x.close for x in bars]; current=bars[-1]
    sma=sum(closes[-cfg.sma:])/cfg.sma
    prior=sum(closes[-cfg.sma-3:-3])/cfg.sma
    prev=bars[-cfg.lookback-1:-1]
    baseline=sum(x.volume for x in prev)/cfg.lookback
    tr=[max(b.high-b.low,abs(b.high-a.close),abs(b.low-a.close)) for a,b in zip(bars,bars[1:])]
    atr=sum(tr[:cfg.atr_period])/cfg.atr_period
    for value in tr[cfg.atr_period:]: atr=(atr*(cfg.atr_period-1)+value)/cfg.atr_period
    trend=current.close>sma>prior
    breakout=current.close>max(x.high for x in prev)
    volume=baseline>0 and current.volume>=cfg.volume_multiple*baseline
    stop=tick(current.close-cfg.stop_atr*atr,step=current.tick_paise)
    target=tick(current.close+cfg.target_r*(current.close-stop),True,current.tick_paise)
    return dict(eligible=bool(trend and breakout and volume and atr>0 and stop>0),
                reason='Rules passed' if trend and breakout and volume and stop>0 else 'No setup: one or more rules failed',
                sma=sma, prior_sma=prior, previous_high=max(x.high for x in prev),
                volume_mean=baseline,volume_ratio=current.volume/baseline if baseline else None,
                atr=atr,trend=trend,breakout=breakout,volume=volume,reference=current.close,stop=stop,target=target)

def import_csv(content):
    rows=[]; errors=[]; seen={}; last={}
    required={'instrument','symbol','timestamp','open','high','low','close','volume','source','interval','adjustment','tick_paise'}
    reader=csv.DictReader(io.StringIO(content))
    if not required.issubset(reader.fieldnames or []): return [],['Missing columns: '+', '.join(sorted(required-set(reader.fieldnames or [])))]
    for n,row in enumerate(reader,2):
        try:
            bar=Candle(instrument=row['instrument'],symbol=row['symbol'],end=stamp(row['timestamp']),
                **{k:money(row[k]) for k in ['open','high','low','close']},volume=int(row['volume']),
                source=row['source'], interval=int(row['interval']),adjustment=row['adjustment'],tick_paise=int(row['tick_paise']))
            key=(bar.instrument,bar.time)
            if key in seen: raise ValueError('Duplicate candle (including identical duplicates)')
            if bar.instrument in last and bar.end<=last[bar.instrument]: raise ValueError('Out-of-order candle')
            seen[key]=bar; last[bar.instrument]=bar.end; rows.append(bar)
        except Exception as e: errors.append(f'Row {n}: {str(e).splitlines()[0]}')
    return ([] if errors else rows),errors
