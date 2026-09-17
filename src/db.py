import sqlite3, json
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

class Database:
    def __init__(self,path='data/paper.db'):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        c=self.connect()
        try:
            version=c.execute('PRAGMA user_version').fetchone()[0]
            if version>2: raise ValueError('Database schema is newer than this application')
            if version==1:
                backup=self.path.with_name(self.path.stem+'.before-v2-'+datetime.now().strftime('%Y%m%d%H%M%S%f')+'.db')
                dest=sqlite3.connect(backup)
                try: c.backup(dest)
                finally: dest.close()
            c.executescript(Path(__file__).with_name('schema.sql').read_text())
            if version<2:
                migration=Path(__file__).with_name('migrations').joinpath('002_research.sql').read_text()
                c.execute('BEGIN IMMEDIATE')
                if c.execute('PRAGMA user_version').fetchone()[0]<2:
                    for statement in migration.split(';'):
                        if statement.strip(): c.execute(statement)
                c.commit()
        finally: c.close()
    def connect(self):
        c=sqlite3.connect(self.path,timeout=15,isolation_level=None)
        c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA busy_timeout=15000')
        return c
    @contextmanager
    def transaction(self):
        c=self.connect()
        try:
            c.execute('BEGIN IMMEDIATE'); yield c; c.commit()
        except BaseException: c.rollback(); raise
        finally: c.close()
    def rows(self,sql,args=()):
        c=self.connect()
        try: return [dict(r) for r in c.execute(sql,args)]
        finally: c.close()
    def backup(self,path):
        path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
        if path.resolve()==self.path.resolve() or path.exists(): raise ValueError('Choose a new backup file')
        source=self.connect(); target=sqlite3.connect(path)
        try: source.backup(target)
        finally: source.close(); target.close()
        return path
    @staticmethod
    def restore(source,target):
        target=Path(target)
        if target.exists(): raise ValueError('Restore only to a NEW database; preserve existing journals')
        c=sqlite3.connect(f'file:{Path(source).resolve().as_posix()}?mode=ro',uri=True)
        try:
            if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or c.execute('PRAGMA foreign_key_check').fetchall(): raise ValueError('Invalid backup')
            if c.execute('PRAGMA user_version').fetchone()[0] not in (1,2): raise ValueError('Unsupported schema')
            target.parent.mkdir(parents=True,exist_ok=True)
            dest=sqlite3.connect(target)
            try: c.backup(dest)
            finally: dest.close()
        finally: c.close()
