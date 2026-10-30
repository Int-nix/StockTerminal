"""Account paper engine: server owns trades; local engine owns only quote cache."""
import uuid
from core.paper import PaperTradingEngine
from core.account_cloud import Cloud

class CloudPaperEngine(PaperTradingEngine):
    def __init__(self, session):
        # Local engine is used only for quote cache, never as account trade storage.
        super().__init__()
        self.cloud = Cloud(session)
        self._state = None
        self.refresh_state()

    def refresh_state(self):
        self._state = self.cloud.request('GET', '/account/paper')
        return self._state

    def account(self):
        return dict(self.refresh_state()['account'])

    def positions(self):
        return list(self.refresh_state()['positions'])

    def get_position(self, ticker):
        return next((p for p in self.positions() if p['ticker'] == ticker.upper()), None)

    def trades(self, limit=500):
        return list(self.refresh_state()['trades'])[:limit]

    def execute_trade(self, ticker, side, shares, price, quote_time=None, note=''):
        order = {'order_id': str(uuid.uuid4()), 'ticker': ticker, 'side': side,
                 'shares': shares, 'price': price, 'quote_time': quote_time, 'note': note}
        # On network ambiguity the server may have committed the order. Never
        # automatically generate a new ID and retry a failed submission.
        result = self.cloud.request('POST', '/account/paper/orders', order)
        self.refresh_state()
        return result['trade']

    def record_equity(self):
        self.cloud.request('POST', '/account/paper/equity')

    def equity_history(self):
        return list(self.refresh_state()['equity_history'])

    def summary(self):
        state = self.refresh_state()
        acct = state['account']
        positions = state['positions']
        prices = self.cached_prices()
        market_value = sum(float(p['shares']) * float(prices.get(p['ticker'], {}).get('price', p['average_cost'])) for p in positions)
        cost_basis = sum(float(p['shares']) * float(p['average_cost']) for p in positions)
        realized = float(state['realized_pl'])
        cash = float(acct['cash'])
        equity = cash + market_value
        start = float(acct['starting_cash'])
        return {'cash': cash, 'starting_cash': start, 'market_value': market_value,
                'cost_basis': cost_basis, 'equity': equity,
                'unrealized_pl': market_value - cost_basis, 'realized_pl': realized,
                'total_return': (equity / start - 1) * 100 if start else 0}
