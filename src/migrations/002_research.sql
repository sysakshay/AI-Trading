CREATE TABLE research_items(id TEXT PRIMARY KEY, run TEXT NOT NULL REFERENCES runs(id), instrument TEXT NOT NULL REFERENCES instruments(id), published TEXT NOT NULL, available TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL);
CREATE INDEX research_asof ON research_items(run,instrument,available,published);
CREATE TABLE experiments(id TEXT PRIMARY KEY, source_run TEXT NOT NULL REFERENCES runs(id), manifest TEXT NOT NULL, state TEXT NOT NULL, created TEXT NOT NULL, completed TEXT, error TEXT);
CREATE TABLE experiment_runs(experiment TEXT NOT NULL REFERENCES experiments(id), variant TEXT NOT NULL, run TEXT NOT NULL UNIQUE REFERENCES runs(id), PRIMARY KEY(experiment,variant));
CREATE TABLE operating_expenses(id TEXT PRIMARY KEY, run TEXT NOT NULL REFERENCES runs(id), time TEXT NOT NULL, category TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount >= 0), note TEXT NOT NULL);
ALTER TABLE worker ADD COLUMN lease_owner TEXT;
INSERT INTO schema_version VALUES(2);
PRAGMA user_version=2;
