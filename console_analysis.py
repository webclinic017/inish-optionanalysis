import os, json, time
import threading
import logging

import data as d
from analysis.correlate import Correlate
from data import store as store
from utils import utils as utils


_logger = utils.get_logger(logging.WARNING)

class Interface:
    def __init__(self, script=''):
        self.technical = None
        self.coorelate = None
        self.exchanges = [e['abbreviation'] for e in d.EXCHANGES]
        self.indexes = [i['abbreviation'] for i in d.INDEXES]
        self.symbols = []

        if script:
            if os.path.exists(script):
                try:
                    with open(script) as file_:
                        data = json.load(file_)
                        print(data)
                except Exception as e:
                    utils.print_error('File read error')
            else:
                utils.print_error(f'File "{script}" not found')
        else:
            self.main_menu()

    def main_menu(self):
        while True:
            menu_items = {
                '1': 'Coorelation',
                '0': 'Exit'
            }

            if self.technical is not None:
                menu_items['1'] = f'Change Symbol ({self.technical.ticker})'

            selection = utils.menu(menu_items, 'Select Operation', 0, 1)

            if selection == 1:
                self.coorelation()
            elif selection == 0:
                break

    def coorelation(self, progressbar=True):
        list = self._get_list()
        if list:
            self.symbols = store.get_symbols(list)
            self.coorelate = Correlate(self.symbols)

            if self.coorelate:
                self.task = threading.Thread(target=self.coorelate.correlate)
                self.task.start()

                if progressbar:
                    print()
                    self._show_progress('Progress', 'Completed')

                utils.print_message(f'Coorelation Among {list} Symbols')
                print(self.coorelate.task_object)
                print(self.coorelate.task_object.min(numeric_only=True))
            else:
                utils.print_error('Invaid symbol list')
                _logger.error(f'{__name__}: Invalid symbol list')

    def _get_list(self):
        list = ''
        menu_items = {}
        for i, exchange in enumerate(self.exchanges):
            menu_items[f'{i+1}'] = f'{exchange}'
        for i, index in enumerate(self.indexes, i):
            menu_items[f'{i+1}'] = f'{index}'
        menu_items['0'] = 'Cancel'

        select = utils.menu(menu_items, 'Select exchange, or 0 to cancel: ', 0, i+1)
        if select > 0:
            list = menu_items[f'{select}']

        return list

    def _show_progress(self, prefix, suffix):
        while not self.coorelate.task_error: pass

        if self.coorelate.task_error == 'None':
            total = self.coorelate.task_total
            utils.progress_bar(self.coorelate.task_completed, self.coorelate.task_total, prefix=prefix, suffix=suffix, length=50, reset=True)
            while self.task.is_alive and self.coorelate.task_error == 'None':
                time.sleep(0.20)
                completed = self.coorelate.task_completed
                symbol = self.coorelate.task_symbol

                utils.progress_bar(completed, total, prefix=prefix, suffix=suffix, symbol=symbol, length=50)



if __name__ == '__main__':
    import argparse

    # Create the top-level parser
    parser = argparse.ArgumentParser(description='Analysis')
    subparser = parser.add_subparsers(help='Specify the desired command')

    # Create the parser for the "load" command
    parser_a = subparser.add_parser('load', help='Load an operation')
    parser_a.add_argument('-t', '--ticker', help='Specify the ticker symbol', required=False, default='IBM')

    # Create the parser for the "execute" command
    parser_b = subparser.add_parser('execute', help='Execute a JSON command script')
    parser_b.add_argument('-f', '--script', help='Specify a script', required=False, default='scripts/script.json')

    command = vars(parser.parse_args())

    if 'script' in command.keys():
        Interface('IBM', script=command['script'])
    elif 'ticker' in command.keys():
        Interface()
    else:
        Interface()
