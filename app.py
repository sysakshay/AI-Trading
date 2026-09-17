from pathlib import Path
import json,os
from datetime import datetime,timedelta
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv
from src.db import Database
from src.engine import Engine,now
from src.domain import Settings,evaluate,import_csv,stamp,money
from src.data import sample,sample_schedule,csv_text,exchange_schedule
from src.ai import Reviewer
from src.reporting import report,export_run,add_expense
from src.research import regime,import_research
from src.experiments import compare,experiment_report

load_dotenv()
st.set_page_config(page_title='Paper Research | NSE lab',page_icon='📊',layout='wide')
st.title('Paper Research')
st.caption('Version 0.2 · A local research journal · NSE cash equities · virtual money only')
db=Database(os.getenv('PAPER_DB','data/paper.db')); engine=Engine(db)

with st.sidebar:
    st.header('Your research desk')
    runs=db.rows('SELECT id,mode,created FROM runs ORDER BY created DESC')
    if st.button('Start offline demo',type='primary'):
        run=engine.create(sample(),sample_schedule())
        for _ in range(28): engine.advance(run)
        Reviewer(engine).review_pending(run)
        st.session_state['selected_run']=run; st.rerun()
    if not runs:
        st.info('Start the offline demo. No keys or accounts needed.')
        st.stop()
    ids=[x['id'] for x in runs]
    selected=st.session_state.get('selected_run',ids[0])
    run=st.selectbox('Saved run',ids,index=ids.index(selected) if selected in ids else 0,
        format_func=lambda x:next(r['mode']+' · '+r['created'][:16]+' · '+x[:6] for r in runs if r['id']==x))
    st.session_state['selected_run']=run
    r=engine.run(run); cfg=Settings.model_validate_json(r['config'])
    st.write('**Mode:** '+r['mode']); st.write('**AI:** '+cfg.ai_mode.upper())
    st.write('**Replay clock (IST):** '+(r['cursor'] or 'Not started'))
    if r['mode']!='FORWARD' and st.button('Advance one candle'):
        t=engine.advance(run)
        if t: Reviewer(engine).review_pending(run)
        st.session_state['notice']='Advanced to '+t if t else 'End of available data. Open positions remain unresolved if no exit observation exists.'
        st.rerun()
    if st.button('Resume entries' if r['paused'] else 'Pause entries'):
        engine.pause(run,not r['paused']); st.rerun()
    st.caption('Pause blocks new entries. Exits continue when replay advances or the forward worker receives data.')
    st.page_link('https://docs.streamlit.io',label='About this local interface')

if 'notice' in st.session_state: st.info(st.session_state.pop('notice'))
contains_synthetic=bool(db.rows("SELECT 1 FROM candles WHERE run=? AND json_extract(payload,'$.source')='SYNTHETIC' LIMIT 1",(run,)))
if r['mode']=='SAMPLE' or contains_synthetic: st.warning('SYNTHETIC DEMONSTRATION · Invented instruments and scenarios. These results do not measure a trading edge.')
elif r['mode']=='FORWARD': st.info('FORWARD PAPER · Coarse completed-candle simulation. Refresh shows worker updates.')
else: st.info('HISTORICAL '+r['mode']+' · Results depend on data quality, costs and fill assumptions.')
rep=report(db,run)
with db.transaction() as c: account=engine.account(c,run,r['cursor'])
cols=st.columns(4)
for col,label,value in zip(cols,['Virtual equity','Available cash','Reserved cash','Realized result'],[account['equity'],account['cash']-account['reserved'],account['reserved'],rep['net_realized_paise']]): col.metric(label,f'INR {value/100:,.2f}')
if account['stale']: st.error('Position marks are stale. Account valuation is uncertain and new entries are blocked.')
tabs=st.tabs(['Watchlist & setups','Positions','Journal','Evaluation','Settings & data'])
with tabs[0]:
    visible=engine.bars(run,upto=r['cursor']) if r['cursor'] else []
    symbols=sorted(set(b.instrument for b in visible))
    watch=[]
    for symbol in symbols:
        bars=[b for b in visible if b.instrument==symbol]; evidence=evaluate(bars,cfg)
        watch.append({'Instrument':symbol,'Close INR':bars[-1].close/100,'Volume':bars[-1].volume,'Volume ratio':evidence.get('volume_ratio'),'Market condition':regime(bars,cfg)['label'],'Status':evidence['reason'],'Evaluated IST':bars[-1].time})
    st.dataframe(watch,width='stretch',hide_index=True)
    if symbols:
        instrument=st.selectbox('Chart instrument',symbols)
        bars=[b for b in visible if b.instrument==instrument]
        fig=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.75,.25],vertical_spacing=.04)
        fig.add_trace(go.Candlestick(x=[b.end for b in bars],open=[b.open/100 for b in bars],high=[b.high/100 for b in bars],low=[b.low/100 for b in bars],close=[b.close/100 for b in bars],name='Price INR'),row=1,col=1)
        fig.add_trace(go.Bar(x=[b.end for b in bars],y=[b.volume for b in bars],name='Volume'),row=2,col=1)
        fig.update_layout(height=470,xaxis_rangeslider_visible=False,margin=dict(l=10,r=10,t=20,b=10))
        st.plotly_chart(fig,width='stretch')
    st.subheader('Proposals awaiting your decision')
    candidates=db.rows('SELECT * FROM candidates WHERE run=? ORDER BY time DESC,instrument',(run,))
    active=[p for p in candidates if p['state'] in ['AWAITING_APPROVAL','PENDING_REVIEW','APPROVED','FAILED']]
    if not active: st.info('No pending setup. No trade is a valid result. Advance replay to evaluate the next candle.')
    for p in active:
        with st.expander(p['instrument']+' · '+p['state']+' · '+p['time'],expanded=p['state']=='AWAITING_APPROVAL'):
            st.write(f"Stop INR {p['stop']/100:.2f} · Target INR {p['target']/100:.2f} · Approval expires {p['expiry']}")
            st.caption('Planning levels only. Entry uses a later completed close, with costs, slippage and all limits checked again.')
            measured=json.loads(p['evidence']); research=measured.get('research')
            if research:
                st.write('**Research desk · '+research['regime']['label']+'**')
                st.caption(research['method'])
                bull,bear=st.columns(2)
                with bull:
                    st.write('**Supporting case**')
                    for item in research['bull_case']: st.write('• '+item['claim'])
                with bear:
                    st.write('**Opposing case**')
                    for item in research['bear_case']: st.write('• '+item['claim'])
                if research['missing_evidence']: st.info('; '.join(research['missing_evidence']))
                st.caption(research['risk_review']['authority'])
                if research['sources']:
                    with st.expander('Timestamped research sources (user supplied)'): st.json(research['sources'])
            else: st.caption('Legacy candidate: original evidence preserved; no retrospective research added.')
            st.json(measured,expanded=False)
            reviews=db.rows('SELECT * FROM reviews WHERE candidate=?',(p['id'],))
            for review in reviews:
                if review['response']:
                    output=json.loads(review['response']); st.write(output['summary']); st.write('Risk factors: '+'; '.join(output['risk_factors']))
                else: st.error('Review '+review['status']+': '+str(review['error']))
                with st.expander('Exact information supplied to AI'): st.json(json.loads(review['context']))
            enabled=p['state']=='AWAITING_APPROVAL' and not r['paused']
            if r['mode']=='FORWARD' and stamp(now())>=stamp(p['expiry']): enabled=False
            if not enabled: st.caption('Approval unavailable: '+(p['reason'] or p['state']))
            a,b=st.columns(2)
            if a.button('Approve virtual trade',key='approve'+p['id'],disabled=not enabled):
                ok,message=engine.decide(p['id'],p['revision']); st.session_state['notice']=message; st.rerun()
            if b.button('Reject proposal',key='reject'+p['id'],disabled=p['state']!='AWAITING_APPROVAL'):
                ok,message=engine.decide(p['id'],p['revision'],False); st.session_state['notice']=message; st.rerun()
with tabs[1]:
    st.subheader('Open virtual positions')
    positions=db.rows('SELECT * FROM positions WHERE run=? AND closed IS NULL',(run,))
    if not positions: st.info('No open positions. Approved proposals wait for the next eligible completed candle.')
    for p in positions:
        st.write(f"**{p['instrument']}** · {p['qty']} shares · Entry INR {p['entry']/100:.2f} · Mark INR {p['mark']/100:.2f}")
        st.write(f"Stop INR {p['stop']/100:.2f} · Target INR {p['target']/100:.2f} · Planned risk INR {p['risk']/100:.2f} · Unrealized INR {((p['mark']-p['entry'])*p['qty']-p['entry_fee'])/100:.2f}")
        st.caption('Marked '+p['marked']+(' · EXIT REQUEST PENDING' if p['exit_requested'] else ''))
        if st.button('Request simulated exit',key=p['id'],disabled=bool(p['exit_requested'])): engine.request_exit(p['id']); st.rerun()
    st.dataframe(db.rows('SELECT o.* FROM orders o JOIN candidates c ON c.id=o.candidate WHERE c.run=?',(run,)),width='stretch',hide_index=True)
with tabs[2]:
    st.subheader('Durable journal')
    filter_symbol=st.selectbox('Instrument filter',['All']+sorted(set(p['instrument'] for p in candidates)))
    filter_state=st.selectbox('Decision/state filter',['All']+sorted(set(p['state'] for p in candidates)))
    date_filter=st.text_input('Date filter (YYYY-MM-DD; blank for all)')
    filtered=[p for p in candidates if (filter_symbol=='All' or p['instrument']==filter_symbol) and (filter_state=='All' or p['state']==filter_state) and (not date_filter or p['time'].startswith(date_filter))]
    st.caption('Strategy '+r['strategy']+' · amounts in exported records are integer paise')
    st.dataframe(filtered,width='stretch',hide_index=True)
    st.write('Closed trades'); st.dataframe(db.rows('SELECT * FROM positions WHERE run=? AND closed IS NOT NULL',(run,)),width='stretch')
    st.write('Cash ledger'); st.dataframe(db.rows('SELECT * FROM ledger WHERE run=?',(run,)),width='stretch')
    st.write('Event history'); st.dataframe(db.rows('SELECT time,kind,detail FROM events WHERE run=? ORDER BY id DESC LIMIT 300',(run,)),width='stretch')
    st.download_button('Export complete run (JSON)',export_run(db,run),file_name='paper-run-'+run[:8]+'.json',mime='application/json')
with tabs[3]:
    st.subheader('Evaluation, not a promise of income')
    st.write(f"Completed trades: **{rep['completed_trades']}** · Transaction costs: **INR {rep['transaction_costs_paise']/100:.2f}** · Longest losing sequence: **{rep['longest_losing_sequence']}**")
    if rep['equity_curve']:
        frame=pd.DataFrame(rep['equity_curve']); frame['Equity INR']=frame.value/100; frame['Drawdown INR']=frame.drawdown/100
        st.line_chart(frame.set_index('time')[['Equity INR']]); st.area_chart(frame.set_index('time')[['Drawdown INR']])
    st.json({k:v for k,v in rep.items() if k!='equity_curve'},expanded=False)
    st.write('**Results by market condition at entry**')
    st.dataframe(rep['regime_breakdown'],hide_index=True,width='stretch')
    st.caption(rep['sample_assessment'])
    with st.expander('Daily / weekly report'):
        date=st.date_input('Period starts'); days=st.selectbox('Report interval',[1,7])
        start=str(date)+'T00:00:00+05:30'; end=str(date+timedelta(days=days))+'T00:00:00+05:30'
        period=report(db,run,start,end); st.json({k:v for k,v in period.items() if k!='equity_curve'},expanded=False)
    st.caption('Undefined statistics display as null. Four to eight weeks is an initial observation checkpoint, not proof. Historical AI may know later events from training. MOCK results test plumbing only.')
    with st.form('expense'):
        category=st.selectbox('Operating expense category',['DATA','AI','OTHER'])
        expense=st.number_input('Allocated operating expense INR',min_value=0.0,value=0.0)
        note=st.text_input('Allocation note (no secrets)',max_chars=200)
        expense_key=st.session_state.setdefault('expense_key',__import__('uuid').uuid4().hex)
        if st.form_submit_button('Save operating expense'):
            add_expense(db,run,category,money(expense),note,key=expense_key)
            st.session_state.pop('expense_key',None); st.rerun()
    st.write(f"Recorded operating expenses: INR {rep['operating_costs_paise']/100:.2f} · Realized result after expenses: INR {rep['economic_realized_paise']/100:.2f}")
    st.caption('Expense records are separate from virtual trading cash; INR allocation is entered by you, not an inferred provider invoice.')
    st.subheader('Saved experiments')
    st.caption('Runs rules, mock research and an experimental volatility filter on the FULL selected historical dataset. No paid calls. Mock is not evidence of AI value.')
    if st.button('Run saved policy comparison',disabled=r['mode']=='FORWARD'):
        with st.spinner('Running three isolated virtual accounts...'): compare(engine,run)
        st.rerun()
    saved=db.rows('SELECT id,state FROM experiments WHERE source_run=? ORDER BY created DESC',(run,))
    for experiment in saved:
        result=experiment_report(db,experiment['id'])
        with st.expander('Experiment '+experiment['id'][:10]+' · '+experiment['state'],expanded=True):
            display=[{**x,'net INR':x['net_paise']/100,'drawdown INR':x['drawdown_paise']/100} for x in result['variants']]
            st.dataframe(display,hide_index=True,width='stretch')
            st.download_button('Export experiment',json.dumps(result,indent=2),file_name='experiment-'+experiment['id'][:10]+'.json',key=experiment['id'])
            st.caption('Cash-only reference: zero trading return. No market benchmark or claim of excess return.')
with tabs[4]:
    st.subheader('Connection & operating status')
    st.write('Market data: **NOT VERIFIED**. Use the read-only connection check in USER_SETUP.md before forward mode.')
    connected=db.rows("SELECT COUNT(*) n FROM reviews WHERE model='gpt-5-mini' AND status='VALID'")[0]['n']
    st.write('OpenAI: **'+('Previously verified response; current availability not guaranteed' if connected else 'NOT VERIFIED')+'** · Key '+('configured (hidden)' if os.getenv('OPENAI_API_KEY') else 'missing'))
    st.write('Daily paid allowance: USD '+os.getenv('AI_DAILY_USD','0')+' · '+os.getenv('AI_DAILY_REQUESTS','0')+' requests')
    st.dataframe(db.rows('SELECT * FROM worker WHERE run=?',(run,)),width='stretch')
    st.json(cfg.model_dump(),expanded=False)
    with st.form('newrun'):
        st.write('New sample account — existing history is preserved')
        capital=st.number_input('Virtual starting cash INR',min_value=100,max_value=100000000,value=10000,step=100)
        mode=st.selectbox('Review policy',['mock','rules','mock_fail'])
        regime_policy=st.selectbox('Market-condition policy',['observe','avoid_high_volatility'],help='Observe leaves the strategy unchanged. The experimental filter blocks UNKNOWN/high relative volatility; not proven to improve results.')
        if st.form_submit_button('Create new sample run'):
            st.session_state['selected_run']=engine.create(sample(),sample_schedule(),Settings(initial_paise=capital*100,ai_mode=mode,regime_policy=regime_policy)); st.rerun()
    with st.expander('Import optional timestamped research for replay'):
        st.caption('JSON news/fundamental summaries from sources you may use. Import into a new offline run before its first candidate. Both publication and actual availability times are required; links are never fetched.')
        research_file=st.file_uploader('Research evidence JSON',type=['json'])
        if research_file and st.button('Import research evidence',disabled=r['mode']=='FORWARD'):
            try:
                count=import_research(db,run,json.loads(research_file.getvalue().decode('utf-8-sig')))
                st.success(str(count)+' evidence records imported')
            except (ValueError,TypeError) as exc: st.error(str(exc).splitlines()[0])
    st.download_button('Download example candle CSV',csv_text(sample()),'example-candles.csv','text/csv')
    st.caption('CSV prices are rupees; timestamp means candle END with explicit timezone. Unadjusted only. Do not import split/corporate-action intervals.')
    upload=st.file_uploader('Historical candle CSV',type=['csv'])
    if upload:
        bars,errors=import_csv(upload.getvalue().decode('utf-8-sig'))
        if errors: st.error('\n'.join(errors))
        elif bars:
            start_date=st.date_input('Replay starts',value=min(b.end.date() for b in bars))
            end_date=st.date_input('Replay ends',value=max(b.end.date() for b in bars))
            verified=st.checkbox('I confirmed data rights, unadjusted prices, no corporate actions, and the NSE session calendar for these dates')
            if st.button('Create isolated historical replay',disabled=not verified):
                selected=[b for b in bars if start_date<=b.end.date()<=end_date]
                try:
                    schedule=sample_schedule() if all(b.source=='SYNTHETIC' for b in selected) else exchange_schedule(str(start_date),str(end_date))
                    st.session_state['selected_run']=engine.create(selected,schedule,Settings(ai_mode='rules'),'REPLAY'); st.rerun()
                except ValueError as e: st.error(str(e))
    if st.button('Create consistent database backup'):
        path=db.backup('backups/paper-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.db'); st.success('Backup saved: '+str(path))
    st.caption('Restore to a new file with the documented CLI. Never overwrite an active database. Close this browser tab to leave the app running; Ctrl+C in its terminal shuts down the UI. Forward worker shutdown is separate.')
