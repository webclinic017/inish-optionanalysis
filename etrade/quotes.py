import json

import etrade.auth as auth
from utils import logger

_logger = logger.get_logger()


class Quotes:
    def __init__(self, session):
        if not auth.base_url:
            raise AssertionError('Etrade session not initialized')

        self.session = session

    def quote(self, symbol: str) -> tuple[str, dict]:
        message = 'success'
        url = f'{auth.base_url}/v1/market/quote/{symbol}.json'
        quote_data = None

        response = self.session.get(url)
        if response is not None and response.status_code == 200:
            quote_data = json.loads(response.text)
            parsed = json.dumps(quote_data, indent=2, sort_keys=True)
            _logger.debug(f'{__name__}: {parsed}')

            if quote_data is not None and 'QuoteResponse' in quote_data and 'QuoteData' in quote_data['QuoteResponse']:
                pass
            elif quote_data is not None and 'QuoteResponse' in quote_data \
                    and 'Messages' in quote_data['QuoteResponse'] \
                    and 'Message' in quote_data['QuoteResponse']['Messages'] \
                    and quote_data['QuoteResponse']['Messages']['Message'] is not None:

                for error_message in quote_data['QuoteResponse']['Messages']['Message']:
                    message += ('Error: ' + error_message['description'])
            else:
                message = 'Error: Quote API service error'
        elif response is not None and response.status_code == 400:
            _logger.debug(f'{__name__}: Response: {response.text}')
            quote_data = json.loads(response.text)
            message = f'\nError ({quote_data["Error"]["code"]}): {quote_data["Error"]["message"]}'
        else:
            _logger.debug(f'{__name__}: Response: {response.text}')
            message = 'E*TRADE API service error'

        return message, quote_data