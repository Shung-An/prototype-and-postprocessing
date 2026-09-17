import json
import time
import subprocess
import urllib.request
import urllib.parse
import webbrowser
from pathlib import Path
import datafiles_browser as browser

webbrowser.open = lambda *args, **kwargs: False
root = Path(r'D:\Quantum Squeezing Project\DataFiles')
run = root / '20260916_161548'
print('PIPELINE_PYTHON=' + browser.pipeline_python(), flush=True)
url = browser.launch_html_browser(root, wait=False)
def asset(path):
    return urllib.request.urlopen(url + 'asset?' + urllib.parse.urlencode({'path': str(path)}))
assert b'critical_pairs_running_average.png' in asset(run).read()
assert asset(run / 'critical_pairs_running_average.png').read(8) == b'\x89PNG\r\n\x1a\n'
print('Folder listing and PNG delivery passed', flush=True)
request = urllib.request.Request(url + 'api/rerun', data=json.dumps({'folder_paths': [str(run)]}).encode(), headers={'Content-Type': 'application/json'})
print(urllib.request.urlopen(request).read().decode(), flush=True)
while True:
    status = json.load(urllib.request.urlopen(url + 'api/rerun-status'))
    print(str(status['progress_percent']) + '% ' + status['message'][-500:], flush=True)
    if not status['running']:
        assert status['return_code'] == 0, status
        break
    time.sleep(10)
print('PASS: rerun API completed successfully', flush=True)
