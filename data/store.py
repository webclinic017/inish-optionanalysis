import datetime as dt

from sqlalchemy import create_engine, and_, or_
from sqlalchemy.orm import sessionmaker
import pandas as pd

import data as d
from fetcher import fetcher as fetcher
from fetcher.google import Google
from fetcher.excel import Excel
from utils import utils as utils
from data import models as models

_logger = utils.get_logger()

_master_exchanges = {
    d.EXCHANGES[0]['abbreviation']: set(),
    d.EXCHANGES[1]['abbreviation']: set(),
    d.EXCHANGES[2]['abbreviation']: set()
    }

_master_indexes = {
    d.INDEXES[0]['abbreviation']: set(),
    d.INDEXES[1]['abbreviation']: set(),
    d.INDEXES[2]['abbreviation']: set()
    }

_engine = create_engine(d.ACTIVE_URI, echo=False)
_session = sessionmaker(bind=_engine)


def is_ticker_valid(symbol:str) -> bool:
    with _session() as session:
        e = session.query(models.Security).filter(models.Security.ticker==symbol.upper()).one_or_none()

    return (e is not None)

def is_exchange(exchange:str) -> bool:
    ret = False
    for e in d.EXCHANGES:
        if exchange == e['abbreviation']:
            ret = True
            break

    return ret

def is_index(index:str) -> bool:
    ret = False
    for i in d.INDEXES:
        if index == i['abbreviation']:
            ret = True
            break

    return ret

def is_list(list:str) -> bool:
    ret = False
    if is_exchange(list):
        ret = True
    elif is_index(list):
        ret = True

    return ret

def get_tickers(list:str='') -> list[str]:
    tickers = []

    if not list:
        with _session() as session:
            sym = session.query(models.Security.ticker).filter(models.Security.active).order_by(models.Security.ticker).all()
        tickers = [x[0] for x in sym]
    elif is_exchange(list):
        tickers = get_exchange_tickers(list)
    elif is_index(list):
        tickers = get_index_tickers(list)

    return tickers

def get_exchanges() -> list[str]:
    results = []

    with _session() as session:
        exchange = session.query(models.Exchange.abbreviation).all()
        results = [exc.abbreviation for exc in exchange]

    return results

def get_indexes() -> list[str]:
    results = []

    with _session() as session:
        index = session.query(models.Index.abbreviation).all()
        results = [ind.abbreviation for ind in index]

    return results

def get_exchange_tickers(exchange:str) -> list[str]:
    results = []

    with _session() as session:
        exc = session.query(models.Exchange.id).filter(models.Exchange.abbreviation==exchange.upper()).one()
        if exc is not None:
            symbols = session.query(models.Security).filter(and_(models.Security.exchange_id==exc.id, models.Security.active)).all()
            results = [symbol.ticker for symbol in symbols]
        else:
            raise ValueError(f'Invalid exchange: {exchange}')

    return results

def get_index_tickers(index:str) -> list[str]:
    results = []

    with _session() as session:
        ind = session.query(models.Index.id).filter(models.Index.abbreviation==index.upper()).first()
        if ind is not None:
            symbols = session.query(models.Security).filter(and_(models.Security.active,
                or_(models.Security.index1_id==ind.id, models.Security.index2_id==ind.id, models.Security.index3_id==ind.id))).all()
            results = [symbol.ticker for symbol in symbols]
        else:
            raise ValueError(f'Invalid index: {index}')

    return results

def get_current_price(ticker:str) -> float:
    price = 0.0
    history = get_history(ticker, 5, live=True)
    if history is not None:
        price = history.iloc[-1]['close']

    return price

def get_history(ticker, days:int, live:bool=False) -> pd.DataFrame:
    results = pd.DataFrame
    if live:
        results = fetcher.get_history(ticker, days)
    else:
        with _session() as session:
            symbols = session.query(models.Security.id).filter(and_(models.Security.ticker==ticker.upper(), models.Security.active)).one_or_none()
            if symbols is not None:
                if days < 0:
                    p = session.query(models.Price).filter(models.Price.security_id==symbols.id).order_by(models.Price.date)
                    results = pd.read_sql(p.statement, _engine)
                    if not results.empty:
                        results.drop(['id', 'security_id'], 1, inplace=True)
                        _logger.info(f'{__name__}: Fetched max price history for {ticker}')

                elif days > 1:
                    start = dt.datetime.today() - dt.timedelta(days=days)
                    p = session.query(models.Price).filter(and_(models.Price.security_id==symbols.id, models.Price.date >= start)).order_by(models.Price.date)
                    results = pd.read_sql(p.statement, _engine)
                    if not results.empty:
                        results.drop(['id', 'security_id'], 1, inplace=True)
                        _logger.info(f'{__name__}: Fetched {days} days of price history for {ticker}')

                else:
                    days = 50
                    start = dt.datetime.today() - dt.timedelta(days=days)
                    p = session.query(models.Price).filter(and_(models.Price.security_id==symbols.id, models.Price.date >= start)).order_by(models.Price.date)
                    results = pd.read_sql(p.statement, _engine)
                    if not results.empty:
                        results = results.iloc[-1]
                        _logger.info(f'{__name__}: Fetched current price history for {ticker}')
                    else:
                        _logger.warning(f'{__name__}: No price history for {ticker}')
            else:
                _logger.warning(f'{__name__}: No history found for {ticker}')

    return results

def get_company(ticker, live:bool=False) -> dict:
    results = {}

    if live:
        company = fetcher.get_company_ex(ticker)
        if company is not None:
            try:
                results['name'] = company.info['shortName']
                results['description'] = company.info['longBusinessSummary']
                results['url'] = company.info['website']
                results['sector'] = company.info['sector']
                results['industry'] = company.info['industry']
                results['exchange'] = company.info['exchange']
                results['beta'] = company.info['beta']
                results['indexes'] = ''
                results['precords'] = 0
            except KeyError:
                results = {}
    else:
        results['name'] = ''
        results['description'] = ''
        results['url'] = ''
        results['sector'] = ''
        results['industry'] = ''
        results['exchange'] = ''
        results['indexes'] = ''
        results['precords'] = 0

        with _session() as session:
            symbol = session.query(models.Security).filter(models.Security.ticker==ticker.upper()).one_or_none()
            if symbol is not None:
                company = session.query(models.Company).filter(models.Company.security_id==symbol.id).one_or_none()
                if company is not None:
                    results['name'] = company.name
                    results['description'] = company.description
                    results['url'] = company.url
                    results['sector'] = company.sector
                    results['industry'] = company.industry

                # Exchange
                exc = session.query(models.Exchange.abbreviation).filter(models.Exchange.id==symbol.exchange_id).one_or_none()
                if exc is not None:
                    results['exchange'] = exc.abbreviation

                # Indexes
                results['indexes'] = 'None'
                if symbol.index1_id is not None:
                    index = session.query(models.Index).filter(models.Index.id==symbol.index1_id).one().abbreviation
                    results['indexes'] = index

                    if symbol.index2_id is not None:
                        index = session.query(models.Index).filter(models.Index.id==symbol.index2_id).one().abbreviation
                        results['indexes'] += f', {index}'

                        if symbol.index3_id is not None:
                            index = session.query(models.Index).filter(models.Index.id==symbol.index3_id).one().abbreviation
                            results['indexes'] += f', {index}'

                p = session.query(models.Price).filter(models.Price.security_id==symbol.id).count()
                results['precords'] = p

    return results

def get_exchange_tickers_master(exchange, type:str='google') -> list[str]:
    global _master_exchanges
    symbols = []
    table = None

    if is_exchange(exchange):
        if len(_master_exchanges[exchange]) > 0:
            symbols = _master_exchanges[exchange]
        else:
            if type == 'google':
                table = Google(d.GOOGLE_SHEETNAME_EXCHANGES)
            elif type == 'excel':
                table = Excel(d.EXCEL_SHEETNAME_EXCHANGES)
            else:
                raise ValueError(f'Invalid table type: {type}')

            if table.open(exchange):
                symbols = table.get_column(1)
                _master_exchanges[exchange] = set(symbols)
            else:
                _logger.warning(f'{__name__}: Unable to open index spreadsheet {exchange}')
    else:
        raise ValueError(f'Invalid exchange name: {exchange}')

    return symbols

def get_index_tickers_master(index, type:str='google') -> list[str]:
    global _master_indexes
    table = None
    symbols = []

    if is_index(index):
        if len(_master_indexes[index]) > 0:
            symbols = _master_indexes[index]
        else:
            if type == 'google':
                table = Google(d.GOOGLE_SHEETNAME_INDEXES)
            elif type == 'excel':
                table = Excel(d.EXCEL_SHEETNAME_INDEXES)
            else:
                raise ValueError(f'Invalid spreadsheet type: {type}')

            if table.open(index):
                symbols = table.get_column(1)
                _master_indexes[index] = set(symbols)
            else:
                _logger.warning(f'{__name__}: Unable to open exchange spreadsheet {index}')
    else:
        raise ValueError(f'Invalid index name: {index}')

    return symbols

def get_option_expiry(ticker:str) -> tuple:
    return fetcher.get_option_expiry(ticker)

def get_option_chain(ticker:str) -> tuple:
    return fetcher.get_option_chain(ticker)

def get_treasury_rate(ticker:str='DTB3') -> float:
    # DTB3: Default to 3-Month Treasury Rate
    return fetcher.get_treasury_rate(ticker)


if __name__ == '__main__':
    import sys
    # from logging import DEBUG
    # logger = u.get_logger(DEBUG)

    if len(sys.argv) > 1:
        t = get_history(sys.argv[1], 20)
    else:
        t = get_history('AAPL', 20)
    print(t)
