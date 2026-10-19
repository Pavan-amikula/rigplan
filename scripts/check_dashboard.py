"""Streamlit headless interaction tests; no browser or cloud credentials required."""
from pathlib import Path
from streamlit.testing.v1 import AppTest

app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=90).run()
assert not app.exception, app.exception
app.number_input[0].set_value(5).run()
assert not app.exception, app.exception
app.toggle[0].set_value(False).run()
assert not app.exception, app.exception
app.slider[0].set_value(72).run()
assert not app.exception, app.exception
app.slider[1].set_value(1200).run()
app.selectbox[0].set_value('TS1').run()
assert not app.exception, app.exception
print('Dashboard: initial render, repeats, pairwise toggle, budget, replay and sensor controls passed.')
