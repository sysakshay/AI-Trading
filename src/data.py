"""Data contracts: candle end timestamps, integer paise, explicit session schedule."""
from datetime import datetime, timedelta
import csv, io
from .domain import Candle, IST, stamp

def sample():
    # Hand-designed deterministic software scenarios, not historical NSE performance.
    bars=[]
    days=['2026-09-14','2026-09-15','2026-09-16']
    for instrument in ['DEMO-WIN','DEMO-LOSS','DEMO-SKIP']:
        for day_index,day in enumerate(days):
            for j in range(25):
                t=datetime.fromisoformat(day+'T09:30:00').replace(tzinfo=IST)+timedelta(minutes=15*j)
                p=10000+day_index*100+j*5
                o=p-5; h=p+50; l=p-50; c=p; v=10000
                if day_index==1:
                    if j>=2:
                        p=10300+(j-2)*5; o=p-5; h=p+50; l=p-50; c=p
                    if j==2: v=25000
                    if j==3: o=10300; h=10325; l=10295; c=10300
                    if j==4:
                        if instrument=='DEMO-WIN': o=10305; h=10800; l=10300; c=10750
                        if instrument=='DEMO-LOSS': o=10000; h=10310; l=9900; c=9950
                if instrument=='DEMO-SKIP': v=1000
                bars.append(Candle(instrument=instrument,symbol=instrument,end=t,open=o,high=h,low=l,close=c,volume=v))
    return sorted(bars,key=lambda b:(b.end,b.instrument))

def sample_schedule():
    return {d:{'open':d+'T09:15:00+05:30','close':d+'T15:30:00+05:30'} for d in ['2026-09-14','2026-09-15','2026-09-16']}

def exchange_schedule(start,end):
    import pandas_market_calendars as mcal
    cal=mcal.get_calendar('NSE')
    df=cal.schedule(start_date=start,end_date=end)
    return {str(i.date()):{'open':row.market_open.tz_convert('Asia/Kolkata').isoformat(),
                             'close':row.market_close.tz_convert('Asia/Kolkata').isoformat()} for i,row in df.iterrows()}

def valid_session(bar,schedule):
    day=stamp(bar.end).date().isoformat(); session=schedule.get(day)
    if not session: return False
    start=stamp(session['open']); end=stamp(session['close'])
    return start+timedelta(minutes=15)<=bar.end<=end and (bar.end-start).total_seconds()%900==0

def csv_text(bars):
    out=io.StringIO(); writer=csv.writer(out)
    writer.writerow(['instrument','symbol','timestamp','open','high','low','close','volume','source','interval','adjustment','tick_paise'])
    for b in bars:
        writer.writerow([b.instrument,b.symbol,b.time,*[f'{getattr(b,k)/100:.2f}' for k in ['open','high','low','close']],b.volume,b.source,15,b.adjustment,b.tick_paise])
    return out.getvalue()
