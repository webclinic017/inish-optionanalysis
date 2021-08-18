'''
yfinance: https://github.com/ranaroussi/yfinance
'''

import os
import time
import datetime as dt
import configparser

import quandl as qd
import yfinance as yf
import pandas as pd

from utils import utils as utils

_logger = utils.get_logger()


# Quandl credentials
CREDENTIALS = os.path.join(os.path.dirname(__file__), 'quandl.ini')
config = configparser.ConfigParser()
config.read(CREDENTIALS)
qd.ApiConfig.api_key = config['DEFAULT']['APIKEY']

THROTTLE = 0.050 # Min secs between calls to Yahoo

def validate_ticker(ticker:str) -> bool:
    valid = False

    # YFinance (or pandas) throws exceptions with bad info (YFinance bug)
    try:
        if yf.Ticker(ticker) is not None:
            valid = True
    except:
        valid = False

    return valid

elasped = 0.0
def get_company_ex(ticker:str) -> pd.DataFrame:
    global elasped
    company = None

    # Throttle requests to help avoid being cut off by Yahoo
    while time.perf_counter() - elasped < THROTTLE: time.sleep(THROTTLE)
    elasped = time.perf_counter()

    try:
        company = yf.Ticker(ticker)
        if company is not None:
            # YFinance (or pandas) throws exceptions with bad info (YFinance bug)
            _ = company.info
    except:
        company = None

    return company

def get_history(ticker:str, days:int=-1) -> pd.DataFrame:
    history = None

    company = get_company_ex(ticker)
    if company is not None:
        if days < 0:
            days = 7300 # 20 years
        elif days > 1:
            pass
        else:
            days = 100

        start = dt.datetime.today() - dt.timedelta(days=days)
        end = dt.datetime.today()

        # YFinance (or pandas) throws exceptions with bad info (YFinance bug)
        for _ in range(3):
            try:
                history = company.history(start=f'{start:%Y-%m-%d}', end=f'{end:%Y-%m-%d}')
                if history is not None:
                    history.reset_index(inplace=True)

                    # Lower case columns to make consistent with Postgress column names
                    history.columns = history.columns.str.lower()
                    _logger.info(f'{__name__}: Fetched {days} days of live history of {ticker} starting {start:%Y-%m-%d}')
                    break
            except Exception as e:
                _logger.error(f'{__name__}: Unable to fetch live history of {ticker} starting {start:%Y-%m-%d}: {e}')
                time.sleep(1)
                history = None

    return history

def get_history_q(ticker:str, days:int=-1) -> pd.DataFrame:
    if days < 0:
        days = 7300 # 20 years
    elif days > 1:
        pass
    else:
        days = 100

    start = dt.datetime.today() - dt.timedelta(days=days)

    history = pd.DataFrame()
    history = qd.get(f'EOD/{ticker}')#, start_date=f'{start:%Y-%m-%d}')
    if history is not None:
        history.reset_index(inplace=True)
        history.columns = history.columns.str.lower()

    return history

def get_option_expiry(ticker:str) -> dict:
    company = get_company_ex(ticker)
    value = company.options

    return value

def get_option_chain(ticker:str) -> dict:
    chain = None

    company = get_company_ex(ticker)
    if company is not None:
        chain = company.option_chain

    return chain

_RATINGS = {
    'strongsell': 5,
    'sell': 5,
    'weaksell': 4,
    'underperform': 4,
    'marketunderperform': 4,
    'sectorunderperform': 4,
    'weakbuy': 4,
    'reduce': 4,
    'underweight': 4,
    'hold': 3,
    'neutral': 3,
    'perform': 3,
    'mixed': 3,
    'peerperform': 3,
    'equalweight': 3,
    'overperform': 2,
    'outperform': 2,
    'marketoutperform': 2,
    'sectoroutperform': 2,
    'positive': 2,
    'overweight': 2,
    'sectorperform': 2,
    'marketperform': 2,
    'add': 2,
    'buy': 1,
    'strongbuy': 1,
    }

def get_ratings(ticker:str):
    ratings = pd.DataFrame
    try:
        company = yf.Ticker(ticker)
        if company is not None:
            ratings = company.recommendations
            if ratings is not None:
                end = dt.date.today()
                start = end - dt.timedelta(days=60)
                ratings = ratings.loc[start:end]

                # Normalize rating text
                ratings.reset_index()
                ratings = ratings['To Grade'].replace(' ', '', regex=True)
                ratings = ratings.replace('-', '', regex=True)
                ratings = ratings.replace('_', '', regex=True)
                ratings = ratings.str.lower().tolist()

                # Log any unhandled ranking so we can add it to the ratings list
                [_logger.error(f'{__name__}: Unhandled rating: {r} for {ticker}') for r in ratings if not r in _RATINGS]

                ratings = [r for r in ratings if r in _RATINGS]
                ratings = [_RATINGS[r] for r in ratings]
            else:
                _logger.info(f'{__name__}: No ratings for {ticker}')
        else:
            _logger.warning(f'{__name__}: Unable to get ratings for {ticker}. No company info')
    except Exception as e:
        _logger.error(f'{__name__}: Unable to get ratings for {ticker}: {str(e)}')

    return ratings

def get_treasury_rate(ticker:str) -> float:
    df = pd.DataFrame()
    df = qd.get(f'FRED/{ticker}')
    if df.empty:
        _logger.error(f'{__name__}: Unable to get Treasury Rates from Quandl')
        raise IOError('Unable to get Treasury Rate from Quandl')

    return df['Value'][0] / 100.0


if __name__ == '__main__':
    # from logging import DEBUG
    # _logger = utils.get_logger(DEBUG)
    import sys
    if len(sys.argv) > 1:
        print(get_ratings(sys.argv[1]))
    else:
        print(get_ratings('aapl'))

    # c = get_company_ex('AAPL')
    # c = get_history_q('AAPL', days=-1)

    # start = dt.datetime.today() - dt.timedelta(days=10)
    # df = refresh_history('AAPL', 60)
    # print(yf.download('AAPL'))
    # print(df.history(start=f'{start:%Y-%m-%d}'))
    # print(df.info)
    # print(df.actions)
    # print(df.dividends)
    # print(df.splits)
    # print(df.institutional_holders)
    # print(df.quarterly_financials)
    # print(df.quarterly_balancesheet)
    # print(df.quarterly_balance_sheet)
    # print(df.quarterly_cashflow)
    # print(df.major_holders)
    # print(df.sustainability)
    # print(df.recommendations)
    # print(df.calendar)
    # print(df.isin)
    # print(df.options)
    # print(df.option_chain)


    '''
    Retrieves a company object that may be used to gather numerous data about the company and security.

    Ticker attributes include:
        .info
        .history(start="2010-01-01",  end=”2020-07-21”)
        .actions
        .dividends
        .splits
        .quarterly_financials
        .major_holders
        .institutional_holders
        .quarterly_balance_sheet
        .quarterly_cashflow
        .quarterly_earnings
        .sustainability
        .recommendations
        .calendar
        .isin
        .options
        .option_chain

    :return: <object> YFinance Ticker object
    '''

    ''' Example .info object:
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
