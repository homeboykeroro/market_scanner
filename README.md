py -m venv
pip install -r requirements.txt

pyinstaller nq.spec
pyinstaller es.spec
pyinstaller ym.spec