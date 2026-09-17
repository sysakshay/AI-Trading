import argparse,json,os
from pathlib import Path
from dotenv import load_dotenv
from .db import Database
from .engine import Engine,now
from .domain import Settings,import_csv,stamp
from .data import sample,sample_schedule,csv_text,exchange_schedule
from .ai import Reviewer
from .reporting import report,export_run
from .provider import Upstox
from .worker import Worker
from .experiments import compare,experiment_report
from .research import import_research

def main():
    load_dotenv(); parser=argparse.ArgumentParser(description='Local paper research. No real order operations.')
    parser.add_argument('--db',default='data/paper.db')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('demo-report')
    comparison=sub.add_parser('compare'); comparison.add_argument('--run',required=True)
    research=sub.add_parser('research-import'); research.add_argument('json_file'); research.add_argument('--run',required=True)
    back=sub.add_parser('backtest'); back.add_argument('csv'); back.add_argument('--start',required=True); back.add_argument('--end',required=True); back.add_argument('--schedule'); back.add_argument('--settings')
    restore=sub.add_parser('restore'); restore.add_argument('backup'); restore.add_argument('new_database')
    check=sub.add_parser('data-check'); check.add_argument('--symbol',required=True); check.add_argument('--start',required=True); check.add_argument('--end',required=True)
    feed=sub.add_parser('feed-check'); feed.add_argument('--symbol',required=True)
    calendar=sub.add_parser('calendar'); calendar.add_argument('--start',required=True); calendar.add_argument('--end',required=True)
    forward=sub.add_parser('forward-init'); forward.add_argument('config')
    work=sub.add_parser('worker'); work.add_argument('config'); work.add_argument('--run',required=True)
    args=parser.parse_args()
    if args.command=='restore': Database.restore(args.backup,args.new_database); print('Validated backup restored to new file.'); return
    db=Database(args.db); e=Engine(db)
    if args.command=='compare':
        key=compare(e,args.run); Path('reports').mkdir(exist_ok=True)
        target=Path('reports/experiment-'+key[:12]+'.json')
        target.write_text(json.dumps(experiment_report(db,key),indent=2),encoding='utf-8'); print(target)
    if args.command=='research-import':
        print(import_research(db,args.run,json.loads(Path(args.json_file).read_text(encoding='utf-8-sig'))),'records imported')
    if args.command=='calendar':
        Path('data').mkdir(exist_ok=True)
        Path('data/verified-schedule.json').write_text(json.dumps(exchange_schedule(args.start,args.end),indent=2))
        print('Draft calendar saved. Compare with NSE holiday/special-session circulars before confirming calendar_verified.')
    if args.command=='feed-check':
        provider=Upstox(os.getenv('UPSTOX_ACCESS_TOKEN','')); instrument=provider.lookup(args.symbol)
        bars=provider.completed(instrument,None,now()); received=now()
        if not bars: raise ValueError('No completed intraday data received')
        age=(stamp(received)-bars[-1].end).total_seconds()
        receipt=dict(received_at=received,latest_candle=bars[-1].time,instrument=instrument['instrument_key'],measured_delay_seconds=age,
            supported=0<=age<=60,meaning='Conservative candle-end-to-receipt age. Repeat near several boundaries; no latency guarantee.')
        Path('data').mkdir(exist_ok=True); Path('data/feed-check.json').write_text(json.dumps(receipt,indent=2)); print(json.dumps(receipt,indent=2))
    if args.command=='demo-report':
        Path('reports').mkdir(exist_ok=True); Path('fixtures').mkdir(exist_ok=True)
        Path('fixtures/sample.csv').write_text(csv_text(sample()),encoding='utf-8')
        for mode in ['rules','mock','mock_fail']:
            run=e.create(sample(),sample_schedule(),Settings(ai_mode=mode),'SAMPLE'); e.backtest(run,Reviewer(e) if mode!='rules' else None)
            Path('reports/demo-'+mode+'.json').write_text(json.dumps(report(db,run),indent=2))
            print(mode,run,report(db,run)['net_realized_paise']/100)
    if args.command=='backtest':
        bars,errors=import_csv(Path(args.csv).read_text(encoding='utf-8-sig'))
        if errors: raise ValueError('\n'.join(errors))
        bars=[b for b in bars if args.start<=b.end.date().isoformat()<=args.end]
        schedule=json.loads(Path(args.schedule).read_text()) if args.schedule else exchange_schedule(args.start,args.end)
        cfg=Settings.model_validate_json(Path(args.settings).read_text()) if args.settings else Settings(ai_mode='rules')
        if cfg.ai_mode=='openai': raise ValueError('Paid historical calls disabled')
        run=e.create(bars,schedule,cfg,'BACKTEST'); e.backtest(run,Reviewer(e) if cfg.ai_mode!='rules' else None)
        Path('reports').mkdir(exist_ok=True); Path('reports/backtest-'+run+'.json').write_text(json.dumps(report(db,run),indent=2)); print(run)
    if args.command=='data-check':
        provider=Upstox(os.getenv('UPSTOX_ACCESS_TOKEN',''))
        instrument=provider.lookup(args.symbol); bars=provider.historical(instrument,args.start,args.end)
        if not bars: raise ValueError('No data received: check dates and entitlement')
        receipt=dict(status='Historical access verified only',received_at=now(),latest_candle=bars[-1].time,instrument=instrument,
            count=len(bars),delay='UNVERIFIED: historical data cannot prove live delay',rights='USER MUST VERIFY')
        Path('data').mkdir(exist_ok=True); Path('data/provider-check.json').write_text(json.dumps(receipt,indent=2)); print(json.dumps(receipt,indent=2))
    if args.command in ['forward-init','worker']:
        config=json.loads(Path(args.config).read_text()); provider=Upstox(os.getenv('UPSTOX_ACCESS_TOKEN',''))
        instruments=[provider.lookup(s) for s in config['symbols']]
        if not 1<=len(instruments)<=20: raise ValueError('Watchlist must contain 1 to 20 instruments')
        if args.command=='forward-init':
            bars=[]
            for instrument in instruments: bars.extend(provider.historical(instrument,config['warmup_start'],config['warmup_end']))
            bars.sort(key=lambda b:(b.end,b.instrument))
            schedule=json.loads(Path(config['schedule_path']).read_text())
            run=e.create(bars,schedule,Settings(**config.get('settings',{'ai_mode':'rules'})),'FORWARD')
            Worker(e,provider,run,instruments,config['verification'])
            while e.advance(run,False): pass
            print('Created forward run:',run,'Start worker separately. No past candidates created.')
        else: Worker(e,provider,args.run,instruments,config['verification']).serve()

if __name__=='__main__': main()
