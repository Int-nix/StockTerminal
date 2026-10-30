"""Account watchlists via authenticated API, with offline read-only cache."""
import json
import os
import re
import sqlite3
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

class WatchlistSyncError(Exception):
    pass

class AccountWatchlist:
    def __init__(self, session):
        self.token = session['token']
        self.api_base = session['api_base'].rstrip('/')
        self.username = session['username']
        root = Path(os.environ.get('STOCKTERMINAL_DATA_DIR') or (Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'StockTerminal' / 'data'))
        root.mkdir(parents=True, exist_ok=True)
        self.cache = root / 'account-watchlists.sqlite3'
        with sqlite3.connect(self.cache) as db:
            db.execute('CREATE TABLE IF NOT EXISTS cache (username TEXT PRIMARY KEY COLLATE NOCASE, tickers TEXT NOT NULL)')
            row = db.execute('SELECT tickers FROM cache WHERE username=?', (self.username,)).fetchone()
        self._tickers = json.loads(row[0]) if row else []

    def _request(self, method, tickers=None):
        headers = {'Authorization': 'Bearer ' + self.token, 'Accept': 'application/json'}
        body = None
        if tickers is not None:
            body = json.dumps({'tickers': sorted(set(tickers))}).encode()
            headers['Content-Type'] = 'application/json'
        req = Request(self.api_base + '/account/watchlist', data=body, headers=headers, method=method)
        try:
            with urlopen(req, timeout=4) as resp:
                result = json.load(resp)
            if not isinstance(result.get('tickers'), list):
                raise WatchlistSyncError('Unexpected watchlist response from server.')
            return result['tickers']
        except HTTPError as exc:
            if exc.code == 401:
                raise WatchlistSyncError('Session expired. Sign in again through the launcher.') from exc
            raise WatchlistSyncError(f'Watchlist server returned HTTP {exc.code}.') from exc
        except (URLError, OSError, ValueError) as exc:
            raise WatchlistSyncError('Server unavailable. No watchlist changes were saved. Try again when online.') from exc

    def _save(self, tickers):
        self._tickers = sorted(set(tickers))
        with sqlite3.connect(self.cache) as db:
            db.execute('INSERT OR REPLACE INTO cache (username,tickers) VALUES (?,?)', (self.username, json.dumps(self._tickers)))

    def refresh(self):
        self._save(self._request('GET'))

    def get_watchlist(self):
        return list(self._tickers)

    def _replace(self, tickers):
        if len(tickers) > 200:
            raise WatchlistSyncError('Account watchlist limit is 200 tickers.')
        self._save(self._request('PUT', tickers))

    def add(self, ticker):
        ticker = ticker.strip().upper()
        if not re.fullmatch(r'[A-Z0-9.^=-]{1,20}', ticker):
            raise WatchlistSyncError('Invalid stock ticker.')
        self._replace(set(self._request('GET')) | {ticker})

    def remove(self, ticker):
        self._replace(set(self._request('GET')) - {ticker.strip().upper()})

    def merge(self, tickers):
        normalized = {ticker.strip().upper() for ticker in tickers}
        if any(not re.fullmatch(r'[A-Z0-9.^=-]{1,20}', ticker) for ticker in normalized):
            raise WatchlistSyncError('Local watchlist contains an invalid ticker.')
        self._replace(set(self._request('GET')) | normalized)
