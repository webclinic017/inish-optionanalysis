import json
import datetime as dt

import pandas as pd
from requests_oauthlib import OAuth1Session

import etrade.auth as auth
from utils import logger

_logger = logger.get_logger()

URL_CHAIN = '/v1/market/optionchains.json'
URL_EXPIRY = '/v1/market/optionexpiredate.json'


class Options:
    def __init__(self, session):
        if not auth.base_url:
            raise AssertionError('Etrade session not initialized')

        self.session: OAuth1Session = session
        self.message = ''

    def chain(self,
              symbol: str,
              expiry_month: int,
              expiry_year: int,
              strikes: int = 10,
              weekly: bool = False,
              otype: str = 'CALLPUT') -> tuple[pd.DataFrame, pd.DataFrame]:

        url = auth.base_url + URL_CHAIN
        self.message = 'error'
        params = {
            'chainType': f'{otype}',
            'noOfStrikes': f'{strikes}',
            'includeWeekly': f'{str(weekly)}',
            'expiryMonth': f'{expiry_month}',
            'expiryYear': f'{expiry_year}',
            'symbol': f'{symbol}'
        }
        chain_data = None

        response = self.session.get(url, params=params)

        if response is not None and response.status_code == 200:
            chain_data = json.loads(response.text)
            if chain_data is not None and 'OptionChainResponse' in chain_data and 'OptionPair' in chain_data['OptionChainResponse']:
                self.message = 'success'
                parsed = json.dumps(chain_data, indent=2, sort_keys=True)
                _logger.debug(f'{__name__}: {parsed}')
        elif response is not None and response.status_code == 400:
            _logger.debug(f'{__name__}: Response Body: {response}')
            chain_data = json.loads(response.text)
            self.message = f'\nError ({chain_data["Error"]["code"]}): {chain_data["Error"]["message"]}'
        else:
            _logger.debug(f'{__name__}: Response Body: {response}')
            self.message = 'E*TRADE API service error'

        table_calls = pd.DataFrame()
        table_puts = pd.DataFrame()
        if self.message == 'success':
            data = chain_data['OptionChainResponse']['OptionPair']

            calls = [item['Call'] for item in data]
            table_calls = pd.DataFrame(calls)
            table_calls.drop(['OptionGreeks', 'quoteDetail'], axis=1, inplace=True)

            puts = [item['Put'] for item in data]
            table_puts = pd.DataFrame(puts)
            table_puts.drop(['OptionGreeks', 'quoteDetail'], axis=1, inplace=True)

        return table_calls, table_puts

    def expiry(self, symbol: str) -> pd.DataFrame:
        self.message = 'error'
        expiry_data = {}

        url = auth.base_url + URL_EXPIRY
        params = {
            'symbol': f'{symbol}'
        }

        response = self.session.get(url, params=params)

        if response is not None and response.status_code == 200:
            expiry_data = json.loads(response.text)
            if expiry_data is not None and 'OptionExpireDateResponse' in expiry_data and 'ExpirationDate' in expiry_data['OptionExpireDateResponse']:
                self.message = 'success'
                parsed = json.dumps(expiry_data, indent=2, sort_keys=True)
                _logger.debug(f'{__name__}: {parsed}')
        elif response is not None and response.status_code == 400:
            _logger.debug(f'{__name__}: Response Body: {response}')
            expiry_data = json.loads(response.text)
            self.message = f'\nError ({expiry_data["Error"]["code"]}): {expiry_data["Error"]["message"]}'
        else:
            _logger.debug(f'{__name__}: Response Body: {response}')
            self.message = 'E*TRADE API service error'

        table = pd.DataFrame()
        if self.message == 'success':
            expiry_data = expiry_data['OptionExpireDateResponse']['ExpirationDate']
            data = [(dt.datetime(item['year'], item['month'], item['day'], 0, 0, 0), item['expiryType'].title()) for item in expiry_data]
            table = pd.DataFrame(data, columns=['date', 'expiryType'])

        return table

'''
Sample OptionChainResponse response

{
  "OptionChainResponse": {
    "OptionPair": [
      {
        "Call": {
          "OptionGreeks": {
            "currentValue": true,
            "delta": 0.6355,
            "gamma": 0.0345,
            "iv": 0.3988,
            "rho": 0.0383,
            "theta": -0.0754,
            "vega": 0.1051
          },
          "adjustedFlag": false,
          "ask": 6.2,
          "askSize": 43,
          "bid": 5.95,
          "bidSize": 461,
          "displaySymbol": "COP May 20 '22 $97 Call",
          "inTheMoney": "y",
          "lastPrice": 0.0,
          "netChange": 0.0,
          "openInterest": 0,
          "optionCategory": "STANDARD",
          "optionRootSymbol": "COP",
          "optionType": "CALL",
          "osiKey": "COP---220520C00097000",
          "quoteDetail": "https://api.etrade.com/v1/market/quote/COP:2022:5:20:CALL:97.000000.json",
          "strikePrice": 97.0,
          "symbol": "COP",
          "timeStamp": 1650561786,
          "volume": 0
        }
      },
      {
          "Put": ...
      }
    ]
  }
'''

'''
Sample OptionDateResponse response

{
  "OptionExpireDateResponse": {
    "ExpirationDate": [
      {
        "day": 22,
        "expiryType": "WEEKLY",
        "month": 4,
        "year": 2022
      },
      {
          ...
      }
    ]
  }
}
'''