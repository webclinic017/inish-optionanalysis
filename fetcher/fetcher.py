'''
yfinance: https://github.com/ranaroussi/yfinance
'''

import time
import datetime as dt
import configparser
import socket
from pathlib import Path

import quandl as qd
import yfinance as yf
import pandas as pd

import fetcher as f
import data as d
import etrade.auth as auth
from etrade.options import Options
from utils import ui, logger


_THROTTLE_FETCH = 0.10  # Min secs between calls to fetch pricing
_THROTTLE_ERROR = 1.00  # Min secs between calls after error
_RETRIES = 2            # Number of fetch retries after error

_logger = logger.get_logger()
_last_company: pd.DataFrame = pd.DataFrame()
_last_ticker: str = ''
_elapsed = 0.0

# Quandl credentials
CREDENTIALS = Path(__file__).resolve().parent  / 'quandl.ini'
config = configparser.ConfigParser()
config.read(CREDENTIALS)
qd.ApiConfig.api_key = config['DEFAULT']['APIKEY']


def is_connected(hostname: str = 'google.com') -> bool:
    try:
        host = socket.gethostbyname(hostname)
        s = socket.create_connection((host, 80), 2)
        s.close()
    except Exception:
        return False
    else:
        return True


_connected = is_connected()


def validate_ticker(ticker: str) -> bool:
    if not _connected:
        raise ConnectionError('No internet connection')

    valid = False

    # YFinance (or Pandas) throws exceptions with bad info (YFinance bug?)
    try:
        _logger.info(f'{__name__}: Fetching Yahoo ticker information for {ticker}...')
        if yf.Ticker(ticker) is not None:
            valid = True
    except Exception:
        valid = False

    return valid


def get_history_live(ticker: str, days: int = -1) -> pd.DataFrame:
    if not _connected:
        raise ConnectionError('No internet connection')

    # Throttle requests to help avoid being cut off by data provider
    global _elapsed
    while (time.perf_counter() - _elapsed) < _THROTTLE_FETCH:
        time.sleep(_THROTTLE_FETCH)
    _elapsed = time.perf_counter()

    _logger.info(f'{__name__}: Fetching {ticker} history from {d.ACTIVE_HISTORYDATASOURCE}...')

    if d.ACTIVE_HISTORYDATASOURCE == 'yfinance':
        history = _get_history_yfinance(ticker, days=days)
    elif d.ACTIVE_HISTORYDATASOURCE == 'quandl':
        history = _get_history_quandl(ticker, days=days)
    else:
        raise ValueError('Invalid data source')

    if history is None:
        history = pd.DataFrame()
        _logger.error(f'{__name__}: \'None\' object for {ticker} (2)')
    elif history.empty:
        _logger.info(f'{__name__}: Empty live history for {ticker}')

    return history


def get_company_live(ticker: str) -> dict:
    company = {}

    c = _get_yfinance_live(ticker)
    if c is not None:
        company = c.info

    return company

def get_option_expiry(ticker: str) -> tuple[str]:
    if not _connected:
        raise ConnectionError('No internet connection')

    if d.ACTIVE_OPTIONDATASOURCE == 'yfinance':
        expiry = _get_option_expiry_yfinance(ticker)
    elif d.ACTIVE_OPTIONDATASOURCE == 'etrade':
        expiry = _get_option_expiry_etrade(ticker)
    else:
        raise ValueError('Invalid data source')

    _logger.debug(f'{__name__}: Expiries: {expiry}')

    return expiry


def get_option_chain(ticker: str, expiry: dt.datetime) -> pd.DataFrame:
    if not _connected:
        raise ConnectionError('No internet connection')

    chain = pd.DataFrame()
    if d.ACTIVE_OPTIONDATASOURCE == 'yfinance':
        chain = _get_option_chain_yfinance(ticker, expiry)
    elif d.ACTIVE_OPTIONDATASOURCE == 'etrade':
        chain = _get_option_chain_etrade(ticker, expiry)
    else:
        raise ValueError('Invalid data source')

    _logger.debug(f'{__name__}: Chain:\n{chain}')

    return chain


def get_ratings(ticker: str) -> list[int]:
    if not _connected:
        raise ConnectionError('No internet connection')

    if d.ACTIVE_OPTIONDATASOURCE == 'etrade':
        _logger.warning(f'{__name__}: Option datasource is E*Trade but using YFinance to fetch ratings')

    ratings = pd.DataFrame()
    results = []
    try:
        _logger.info(f'{__name__}: Fetching Yahoo rating information for {ticker}...')
        company = yf.Ticker(ticker)
        if company is not None:
            ratings = company.recommendations
            if ratings is not None and not ratings.empty:
                # Clean up and normalize text
                ratings = ratings.reset_index()
                ratings = ratings.sort_values('Date', ascending=True)
                ratings = ratings.tail(10)
                ratings = ratings['To Grade'].replace(' ', '', regex=True)
                ratings = ratings.replace('-', '', regex=True)
                ratings = ratings.replace('_', '', regex=True)

                results = ratings.str.lower().tolist()

                # Log any unhandled ranking so we can add it to the ratings list
                [_logger.warning(f'{__name__}: Unhandled rating: {r} for {ticker}') for r in results if not r in f.RATINGS]

                # Use the known ratings and convert to their numeric values
                results = [r for r in results if r in f.RATINGS]
                results = [f.RATINGS[r] for r in results]
            else:
                _logger.info(f'{__name__}: No ratings for {ticker}')
        else:
            _logger.info(f'{__name__}: Unable to get ratings for {ticker}. No company info')
    except Exception as e:
        results = []
        _logger.error(f'{__name__}: Unable to get ratings for {ticker}: {str(e)}')

    return results


def get_treasury_rate(ticker: str) -> float:
    if not _connected:
        raise ConnectionError('No internet connection')

    df = pd.DataFrame()
    df = qd.get(f'FRED/{ticker}')
    if df.empty:
        _logger.error(f'{__name__}: Unable to get Treasury Rates from Quandl')
        raise IOError('Unable to get Treasury Rate from Quandl')

    return df['Value'][0] / 100.0


def _get_yfinance_live(ticker: str) -> yf.Ticker:
    global _last_company, _last_ticker

    if not _connected:
        raise ConnectionError('No internet connection')

    if ticker == _last_ticker:
        company = _last_company
        _logger.info(f'{__name__}: Using cached company information for {ticker} from Yahoo')
    else:
        company = yf.Ticker(ticker)
        _logger.info(f'{__name__}: Fetched live company information for {ticker} from Yahoo')

    _last_company = company
    _last_ticker = ticker

    return company


def _get_history_yfinance(ticker: str, days: int = -1) -> pd.DataFrame:
    if not _connected:
        raise ConnectionError('No internet connection')

    history: pd.DataFrame = pd.DataFrame()
    company = _get_yfinance_live(ticker)

    if company is None:
        _logger.error(f'{__name__}: \'None\' object for {ticker} (1)')
    else:
        if days < 0:
            days = 7300  # 20 years

        if days > 0:
            end = dt.datetime.today()
            start = end - dt.timedelta(days=days)

            for retry in range(_RETRIES):
                try:
                    kwargs = {'debug': False}
                    history = company.history(start=start, end=end, interval='1d', timeout=2.0, back_adjust=True, **kwargs)

                    if history is None:
                        history = pd.DataFrame()
                        _logger.warning(f'{__name__}: {d.ACTIVE_HISTORYDATASOURCE} history for {ticker} is None ({retry+1})')
                        time.sleep(_THROTTLE_ERROR)
                    elif history.empty:
                        _logger.warning(f'{__name__}: {d.ACTIVE_HISTORYDATASOURCE} history for {ticker} is empty ({retry+1})')
                        time.sleep(_THROTTLE_ERROR)
                    elif history.shape[1] == 0:
                        history = pd.DataFrame()
                        _logger.warning(f'{__name__}: {d.ACTIVE_HISTORYDATASOURCE} history for {ticker} has no columns ({retry+1})')
                        time.sleep(_THROTTLE_ERROR)
                    else:
                        days = history.shape[0]
                        history = history.reset_index()

                        # Clean some things up and make colums consistent with Postgres column names
                        history.columns = history.columns.str.lower()
                        history = history.drop(['dividends', 'stock splits'], axis=1)
                        history = history.sort_values('date', ascending=True)

                        _logger.info(f'{__name__}: {ticker} Fetched {days} days of live history of {ticker} starting {start:%Y-%m-%d}')
                        break
                except Exception as e:
                    _logger.error(f'{__name__}: Exception: {e}: During attempt {retry+1} to fetch history of {ticker} from {d.ACTIVE_HISTORYDATASOURCE}')
                    history = pd.DataFrame()
                    time.sleep(_THROTTLE_ERROR)

    return history


def _get_history_quandl(ticker: str, days: int = -1) -> pd.DataFrame:
    if not _connected:
        raise ConnectionError('No internet connection')

    history: pd.DataFrame = pd.DataFrame()

    if days < 0:
        days = 7300  # 20 years

    if days > 0:
        start = dt.datetime.today() - dt.timedelta(days=days)

        for retry in range(_RETRIES):
            try:
                history = qd.get_table(f'QUOTEMEDIA/PRICES',
                                       qopts={'columns': ['date', 'open', 'high', 'low', 'close', 'volume']},
                                       ticker=ticker, paginate=True, date={'gte': f'{start:%Y-%m-%d}'})
                days = history.shape[0]

                if history is None:
                    history = pd.DataFrame()
                    _logger.warning(f'{__name__}: {d.ACTIVE_HISTORYDATASOURCE} history for {ticker} is None ({retry+1})')
                    time.sleep(_THROTTLE_ERROR)
                elif history.empty:
                    _logger.info(f'{__name__}: {d.ACTIVE_HISTORYDATASOURCE} history for {ticker} is empty ({retry+1})')
                    time.sleep(_THROTTLE_ERROR)
                else:
                    history = history.reset_index()

                    # Clean some things up and make columns consistent with Postgres column names
                    history.columns = history.columns.str.lower()
                    history = history.drop(['none'], axis=1)
                    history = history.sort_values('date', ascending=True)

                    _logger.info(f'{__name__}: Fetched {days} days of live history of {ticker} starting {start:%Y-%m-%d}')
                    break
            except Exception as e:
                _logger.error(f'{__name__}: Exception: {e}: Retry {retry} to fetch history of {ticker} from {d.ACTIVE_HISTORYDATASOURCE}')
                history = pd.DataFrame()
                time.sleep(_THROTTLE_ERROR)

    return history


def _get_option_expiry_yfinance(ticker: str) -> tuple[str]:
    expiry = ('',)
    for retry in range(_RETRIES):
        company = _get_yfinance_live(ticker)
        if company is not None:
            expiry = company.options
            break
        else:
            _logger.warning(f'{__name__}: Retry {retry} to fetch option expiry for {ticker} using yfinance')
            time.sleep(_THROTTLE_ERROR)

    return expiry


def _get_option_expiry_etrade(ticker: str) -> tuple[str]:
    if auth.Session is None:
        raise ValueError('Must authorize E*Trade session')

    options = Options()
    expiry_data = options.expiry(ticker)
    expiry = tuple([f'{item.date:%Y-%m-%d}' for item in expiry_data.itertuples()])

    return expiry


def _get_option_chain_yfinance(ticker: str, expiry: dt.datetime) -> pd.DataFrame:
    chain = pd.DataFrame()
    for retry in range(_RETRIES):
        company = _get_yfinance_live(ticker)
        if company is not None:
            chain_c = company.option_chain(expiry.strftime(ui.DATE_FORMAT_YMD)).calls
            chain_c['type'] = 'call'
            chain_p = company.option_chain(expiry.strftime(ui.DATE_FORMAT_YMD)).puts
            chain_p['type'] = 'put'
            chain = pd.concat([chain_c, chain_p], axis=0)

            order = [
                'contractSymbol',
                'symbol',
                'type',
                'strike',
                'lastPrice',
                'inTheMoney',
                'impliedVolatility',
                'volume',
            ]
            chain = chain.reindex(columns=order)

            break
        else:
            _logger.warning(f'{__name__}: Retry {retry} to fetch option chain for {ticker}')
            time.sleep(_THROTTLE_ERROR)

    return chain


def _get_option_chain_etrade(ticker: str, expiry: dt.datetime) -> pd.DataFrame:
    if auth.Session is None:
        raise ValueError('Must authorize E*Trade session')

    chain = pd.DataFrame()
    options = Options()

    year = expiry.year
    month = expiry.month
    chain = options.chain(ticker, month, year)

    rename = {
        'osiKey': 'contractSymbol',
        'strikePrice': 'strike'
    }
    chain = chain.rename(rename, axis=1)

    order = [
        'contractSymbol',
        'symbol',
        'type',
        'strike',
        'lastPrice',
        'inTheMoney',
        'impliedVolatility',
        'volume',
    ]
    chain = chain.reindex(columns=order)

    return chain


if __name__ == '__main__':
    import sys
    import logging
    logger.get_logger(logging.INFO)

    if len(sys.argv) > 1:
        c = _get_yfinance_live(sys.argv[1])
    else:
        c = _get_yfinance_live('MSFT')

    # print(c.mutualfund_holders)
    dates = c.options
    chain = c.option_chain(dates[0])
    print(chain)
    # print(dates)

    '''
    YFinance ticker attributes include:
        .history
        .analysis
        .actions
        .balance_sheet
        .calendar
        .cashflow
        .dividends
        .earnings
        .financials
        .info
        .institutional_holders
        .isin
        .major_holders
        .mutualfund_holders
        .options
        .option_chain
        .quarterly_financials
        .quarterly_balance_sheet
        .quarterly_cashflow
        .quarterly_earnings
        .recommendations
        .splits
        .sustainability
    '''

    ''' Example YFinance .option_chain object:
            'contractSymbol',
            'lastTradeDate',
            'strike',
            'lastPrice',
            'bid',
            'ask',
            'change',
            'percentChange',
            'volume',
            'openInterest',
            'impliedVolatility',
            'inTheMoney',
            'contractSize',
            'currency'])
    '''

    ''' Example YFinance .info object:
    {
        "zip":"98052-6399",
        "sector":"Technology",
        "fullTimeEmployees":163000,
        "longBusinessSummary":"Microsoft Corporation develops, licenses, ...",
        "city":"Redmond",
        "phone":"425-882-8080",
        "state":"WA",
        "country":"United States",
        "companyOfficers":[],
        "website":"http://www.microsoft.com",
        "maxAge":1,
        "address1":"One Microsoft Way",
        "industry":"Software—Infrastructure",
        "previousClose":242.2,
        "regularMarketOpen":243.15,
        "twoHundredDayAverage":215.28839,
        "trailingAnnualDividendYield":0.008835673,
        "payoutRatio":0.31149998,
        "volume24Hr":"None",
        "regularMarketDayHigh":243.68,
        "navPrice":"None",
        "averageDailyVolume10Day":28705283,
        "totalAssets":"None",
        "regularMarketPreviousClose":242.2,
        "fiftyDayAverage":225.23157,
        "trailingAnnualDividendRate":2.14,
        "open":243.15,
        "toCurrency":"None",
        "averageVolume10days":28705283,
        "expireDate":"None",
        "yield":"None",
        "algorithm":"None",
        "dividendRate":2.24,
        "exDividendDate":1613520000,
        "beta":0.816969,
        "circulatingSupply":"None",
        "startDate":"None",
        "regularMarketDayLow":240.81,
        "priceHint":2,
        "currency":"USD",
        "trailingPE":36.151783,
        "regularMarketVolume":17420109,
        "lastMarket":"None",
        "maxSupply":"None",
        "openInterest":"None",
        "marketCap":1828762025984,
        "volumeAllCurrencies":"None",
        "strikePrice":"None",
        "averageVolume":29247585,
        "priceToSalesTrailing12Months":11.930548,
        "dayLow":240.81,
        "ask":242.26,
        "ytdReturn":"None",
        "askSize":900,
        "volume":17420109,
        "fiftyTwoWeekHigh":245.09,
        "forwardPE":29.97157,
        "fromCurrency":"None",
        "fiveYearAvgDividendYield":1.71,
        "fiftyTwoWeekLow":132.52,
        "bid":242.16,
        "tradeable":false,
        "dividendYield":0.0092,
        "bidSize":1100,
        "dayHigh":243.68,
        "exchange":"NMS",
        "shortName":"Microsoft Corporation",
        "longName":"Microsoft Corporation",
        "exchangeTimezoneName":"America/New_York",
        "exchangeTimezoneShortName":"EST",
        "isEsgPopulated":false,
        "gmtOffSetMilliseconds":"-18000000",
        "quoteType":"EQUITY",
        "symbol":"MSFT",
        "messageBoardId":"finmb_21835",
        "market":"us_market",
        "annualHoldingsTurnover":"None",
        "enterpriseToRevenue":11.596,
        "beta3Year":"None",
        "profitMargins":0.33473998,
        "enterpriseToEbitda":24.796,
        "52WeekChange":0.2835188,
        "morningStarRiskRating":"None",
        "forwardEps":8.09,
        "revenueQuarterlyGrowth":"None",
        "sharesOutstanding":7560500224,
        "fundInceptionDate":"None",
        "annualReportExpenseRatio":"None",
        "bookValue":17.259,
        "sharesShort":41952779,
        "sharesPercentSharesOut":0.0056,
        "fundFamily":"None",
        "lastFiscalYearEnd":1593475200,
        "heldPercentInstitutions":0.71844,
        "netIncomeToCommon":51309998080,
        "trailingEps":6.707,
        "lastDividendValue":0.56,
        "SandP52WeekChange":0.15952432,
        "priceToBook":14.048902,
        "heldPercentInsiders":0.00059,
        "nextFiscalYearEnd":1656547200,
        "mostRecentQuarter":1609372800,
        "shortRatio":1.54,
        "sharesShortPreviousMonthDate":1607990400,
        "floatShares":7431722306,
        "enterpriseValue":1777517723648,
        "threeYearAverageReturn":"None",
        "lastSplitDate":1045526400,
        "lastSplitFactor":"2:1",
        "legalType":"None",
        "lastDividendDate":1605657600,
        "morningStarOverallRating":"None",
        "earningsQuarterlyGrowth":0.327,
        "dateShortInterest":1610668800,
        "pegRatio":1.82,
        "lastCapGain":"None",
        "shortPercentOfFloat":0.0056,
        "sharesShortPriorMonth":39913925,
        "impliedSharesOutstanding":"None",
        "category":"None",
        "fiveYearAverageReturn":"None",
        "regularMarketPrice":243.15,
        "logo_url":"https://logo.clearbit.com/microsoft.com"
    }
    '''
