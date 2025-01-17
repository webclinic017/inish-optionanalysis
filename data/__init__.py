import configparser
from pathlib import Path


# Price data sources
VALID_HISTORYDATASOURCES = ('yfinance', 'quandl')
ACTIVE_HISTORYDATASOURCE = VALID_HISTORYDATASOURCES[0]

# Option data sources
VALID_OPTIONDATASOURCES = ('yfinance', 'etrade')
ACTIVE_OPTIONDATASOURCE = VALID_OPTIONDATASOURCES[0]

# Databases
VALID_DBS = ('live', 'Postgres', 'SQLite')
ACTIVE_DB = VALID_DBS[1]

if ACTIVE_DB == VALID_DBS[1]: # Postgres
    CREDENTIALS = Path(__file__).resolve().parent  / 'postgres.ini'
    config = configparser.ConfigParser()
    config.read(CREDENTIALS)
    dbuser = config['DEFAULT']['USER']
    dbpw = config['DEFAULT']['PW']
    port = config['DEFAULT']['PORT']
    db = config['DEFAULT']['DB']
    POSTGRES_URI = f'postgresql+psycopg2://{dbuser}:{dbpw}@localhost:{port}/{db}'
    ACTIVE_URI = POSTGRES_URI
elif ACTIVE_DB == VALID_DBS[2]: # SQLite
    SQLITE_FILE_PATH = 'data/securities.db'
    SQLITE_URI = f'sqlite:///{SQLITE_FILE_PATH}'
    ACTIVE_URI = SQLITE_URI
else:
    ACTIVE_URI = ''

# Symbol master spreadsheets
VALID_SPREADSHEETS = ('google', 'excel')
GOOGLE_SHEETNAME_EXCHANGES = 'Exchanges'
GOOGLE_SHEETNAME_INDEXES = 'Indexes'
EXCEL_SHEETNAME_EXCHANGES = 'data/symbols/exchanges.xlsx'
EXCEL_SHEETNAME_INDEXES = 'data/symbols/indexes.xlsx'

EXCHANGES = ({'abbreviation': 'NASDAQ', 'name': 'National Association of Securities Dealers Automated Quotations'},
             {'abbreviation': 'NYSE',   'name': 'New York Stock Exchange'},
             {'abbreviation': 'AMEX',   'name': 'American Stock Exchange'})

INDEXES = ({'abbreviation': 'SP500',  'name': 'Standard & Poors 500'},
           {'abbreviation': 'DOW',    'name': 'DOW Industrials'})
