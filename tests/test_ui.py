from streamlit.testing.v1 import AppTest
from pathlib import Path

def test_ui_offline_workflow(tmp_path,monkeypatch):
    monkeypatch.setenv('PAPER_DB',str(tmp_path/'ui.db'))
    app=AppTest.from_file(str(Path('app.py').resolve()),default_timeout=30).run()
    assert not app.exception
    next(b for b in app.button if b.label=='Start offline demo').click().run()
    assert not app.exception
    next(b for b in app.button if b.label=='Approve virtual trade' and not b.disabled).click().run()
    assert not app.exception
    next(b for b in app.button if b.label=='Advance one candle').click().run()
    next(b for b in app.button if b.label=='Advance one candle').click().run()
    assert not app.exception
    assert any('INR' in metric.value for metric in app.metric)

def test_ui_saved_experiment_survives_session(tmp_path,monkeypatch):
    monkeypatch.setenv('PAPER_DB',str(tmp_path/'comparison-ui.db'))
    app=AppTest.from_file(str(Path('app.py').resolve()),default_timeout=60).run()
    next(b for b in app.button if b.label=='Start offline demo').click().run()
    assert any('Research desk' in x.value for x in app.markdown)
    next(b for b in app.button if b.label=='Run saved policy comparison').click().run(timeout=60)
    assert not app.exception
    restarted=AppTest.from_file(str(Path('app.py').resolve()),default_timeout=60).run()
    assert not restarted.exception
    # Comparison accounts are saved too; select the original source account explicitly.
    source=app.session_state['selected_run']
    next(s for s in restarted.selectbox if s.label=='Saved run').select(source).run()
    assert any('COMPLETE' in x.label for x in restarted.expander)
