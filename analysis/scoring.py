from data import store as store
from utils import utils

_logger = utils.get_logger()


class ScoringAnalysis:
    def __init__(self, ticker:str):
        if store.is_ticker(ticker):
            self.ticker = ticker.upper()
            self.ema = {}
            self.rsa = None
            self.vwap = None
            self.macd = None
            self.bb = None
        else:
            _logger.error(f'Error initializing {__class__}')

    def __str__(self):
        return f'Scoring Analysis for {self.ticker}'
