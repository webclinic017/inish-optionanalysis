import os
import json
import random
from concurrent import futures
import numpy as np

from base import Threaded
from company.company import Company
from utils import utils as utils
from data import store as store
from .interpreter import Interpreter


_logger = utils.get_logger()

class Result:
    def __init__(self, company:Company, success:list[bool], score:list[float], results:list[str]):
        self.company = company
        self.success = success
        self.score = score
        self.results = results

    def __str__(self):
        return self.company.ticker

    def __bool__(self):
        return all(self.success)

    def __float__(self):
        return float(sum(self.score)) / len(self.score) if len(self.score) > 0 else 0.0

class Screener(Threaded):
    def __init__(self, table:str, script:str='', days:int=365, live:bool=False):
        super().__init__()

        self.table = table.upper()
        self.script_name = script
        self.type = ''

        if self.table == 'ALL':
            self.type = 'all'
        elif store.is_exchange(self.table):
            self.type = 'exchange'
        elif store.is_index(self.table):
            self.type = 'index'
        elif store.is_ticker(table):
            self.type = 'symbol'
        else:
            raise ValueError(f'Table not found: {self.table}')

        if days < 30:
            raise ValueError('Invalid number of days')

        self.days = days
        self.live = live
        self.script = []
        self.companies = []
        self.results = []
        self._concurrency = 10

        if script:
            if not self.load_script(script):
                raise ValueError(f'Script not found or invalid format: {script}')

        self.open()

    def __str__(self):
        return f'{self.table}/{self.script_name}'

    def load_script(self, script:str, init:str='') -> bool:
        self.script = []
        if os.path.exists(script):
            try:
                with open(script) as f:
                    self.script = json.load(f)
            except:
                self.script = None
                _logger.error(f'{__name__}: File format error')
            else:
                if init:
                    self._add_init_script(init)
        else:
            _logger.error(f'{__name__}: File "{script}" not found')

        return bool(self.script)

    def open(self) -> bool:
        tickers = []

        if self.type == 'all':
            tickers = store.get_tickers()
        elif self.type == 'exchange':
            tickers = store.get_exchange_tickers(self.table)
        elif self.type == 'index':
            tickers = store.get_index_tickers(self.table)
        else:
            tickers = [self.table]

        if len(tickers) > 0:
            try:
                self.companies = [Company(s, self.days, live=self.live) for s in tickers]
            except ValueError as e:
                _logger.warning(f'{__name__}: Invalid ticker {s}')

            _logger.debug(f'{__name__}: Opened {self.task_total} symbols from {self.table} table')
        else:
            _logger.debug(f'{__name__}: No symbols available')

        return len(self.companies) > 0

    @Threaded.threaded
    def run_script(self) -> list[str]:
        self.results = []
        self.task_total = len(self.companies)

        if self.task_total == 0:
            self.task_completed = self.task_total
            self.results = []
            self.task_error = 'No symbols'
            _logger.warning(f'{__name__}: {self.task_error}')
        elif len(self.script) == 0:
            self.task_completed = self.task_total
            self.results = []
            self.task_error = 'Illegal script'
            _logger.warning(f'{__name__}: {self.task_error}')
        else:
            self.task_error = 'None'

            self._concurrency = 10 if len(self.companies) > 10 else 1

            # Randomize and split up the lists
            random.shuffle(self.companies)
            lists = np.array_split(self.companies, self._concurrency)
            lists = [i for i in lists if i is not None]

            with futures.ThreadPoolExecutor(max_workers=self._concurrency) as executor:
                self.task_futures = [executor.submit(self._run, list) for list in lists]

            self.task_error = 'Done'

        # Return a list of successful tickers
        return [r.company.ticker for r in self.results if r]

    def _run(self, companies:str) -> None:
        for symbol in companies:
            success = []
            score = []
            result = []
            self.task_ticker = symbol
            for filter in self.script:
                interpreter = Interpreter(symbol, filter)
                try:
                    success += [interpreter.run()]
                    score += [interpreter.score]
                    result += [interpreter.result]
                except SyntaxError as e:
                    self.task_error = str(e)
                    break
                except RuntimeError as e:
                    self.task_error = str(e)
                    break

            if self.task_error == 'None':
                self.task_completed += 1
                self.results += [Result(symbol, success, score, result)]
                if (bool(self.results[-1])):
                    self.task_success += 1
            else:
                self.task_completed = self.task_total
                self.results = []
                break

    def _add_init_script(self, script:str) -> bool:
        if os.path.exists(script):
            try:
                with open(script) as f:
                    script = json.load(f)
                    self.script += script
            except:
                script = None
                _logger.error(f'{__name__}: File format error')
        else:
            _logger.error(f'{__name__}: File "{script}" not found')

        return self.script is not None

    def valid(self) -> bool:
        return bool(self.table)


if __name__ == '__main__':
    import logging

    utils.get_logger(logging.DEBUG)

    s = Screener('DOW')
    s.load_script('/Users/steve/Documents/Source Code/Personal/OptionAnalysis/screener/screens/test.screen')
    # s.run_script()
