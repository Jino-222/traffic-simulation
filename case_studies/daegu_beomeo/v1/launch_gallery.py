"""Run the portable gallery on loopback only; Python standard library."""
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from functools import partial
import argparse,webbrowser
ROOT=Path(__file__).resolve().parent
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8504);p.add_argument('--open',action='store_true');a=p.parse_args()
    url=f'http://127.0.0.1:{a.port}/web/'
    print(url,flush=True)
    with ThreadingHTTPServer(('127.0.0.1',a.port),partial(SimpleHTTPRequestHandler,directory=str(ROOT))) as server:
        if a.open:webbrowser.open(url)
        server.serve_forever()
