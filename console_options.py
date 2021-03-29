import sys, os, json
import logging
import datetime

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as clrs
import matplotlib.ticker as mticker

from strategy.strategy import Leg
from strategy.call import Call
from strategy.put import Put
from strategy.vertical import Vertical
from options.chain import Chain
from company import fetcher as f
from utils import utils as u

MAX_ROWS = 50
MAX_COLS = 18

logger = u.get_logger()


class Interface:
    def __init__(self, ticker, strategy, direction, autoload='', script='', exit=False):
        pd.options.display.float_format = '{:,.2f}'.format

        # Initialize data fetcher
        f.initialize()

        ticker = ticker.upper()
        valid = f.validate_ticker(ticker)

        self.ticker = ticker
        self.strategy = None
        self.dirty_calculate = True
        self.dirty_analyze = True

        if valid:
            self.chain = Chain(ticker)

            if autoload:
                if self.load_strategy(ticker, autoload, direction):
                    if not exit:
                        self.main_menu()
            elif script:
                if os.path.exists(script):
                    try:
                        with open(script) as file_:
                            data = json.load(file_)
                            print(data)
                    except Exception as e:
                        u.print_error('File read error')
                else:
                    u.print_error(f'File "{script}" not found')
            else:
                if not exit:
                    self.strategy = Call(ticker, strategy, direction)
                    self.calculate()
                    self.main_menu()
                else:
                    u.print_error('Nothing to do')
        else:
            u.print_error('Invalid ticker symbol specified')

    def main_menu(self):
        while True:
            menu_items = {
                '1': f'Change Symbol ({self.strategy.ticker})',
                '2': f'Change Strategy ({self.strategy})',
                '3': 'Select Options',
                '4': 'View Option Details',
                '5': 'Calculate Value',
                '6': 'View Value',
                '7': 'Analyze Stategy',
                '8': 'View Analysis',
                '9': 'Settings',
                '0': 'Exit'
            }

            if self.strategy.name == 'vertical':
                menu_items['3'] += f' '\
                    f'(L:${self.strategy.legs[0].option.strike:.2f}{self.strategy.legs[0].option.decorator}'\
                    f' S:${self.strategy.legs[1].option.strike:.2f}{self.strategy.legs[1].option.decorator})'
            else:
                menu_items['3'] += f' (${self.strategy.legs[0].option.strike:.2f}{self.strategy.legs[0].option.decorator})'

            if self.dirty_calculate:
                menu_items['5'] += ' *'

            if self.dirty_analyze:
                menu_items['7'] += ' *'

            self.show_legs()

            selection = u.menu(menu_items, 'Select Operation', 0, 9)

            if selection == 1:
                self.select_symbol()
            elif selection == 2:
                self.select_strategy()
            elif selection == 3:
                if self.select_chain():
                    self.calculate()
                    self.show_options()
            elif selection == 4:
                self.show_options()
            elif selection == 5:
                self.calculate()
            elif selection == 6:
                self.show_value()
            elif selection == 7:
                self.analyze()
            elif selection == 8:
                self.show_analysis()
            elif selection == 9:
                self.select_settings()
            elif selection == 0:
                break

    def show_value(self, val=0):
        if not self.dirty_calculate:
            if len(self.strategy.legs) > 1:
                leg = u.input_integer('Enter Leg: ', 1, 2) - 1
            else:
                leg = 0

            table_ = self.strategy.legs[leg].table
            if table_ is not None:
                if val == 0:
                    val = u.input_integer('(1) Table, (2) Chart, (3) Contour, (4) Surface, or (0) Cancel: ', 0, 4)
                if val > 0:
                        title = f'Value: {self.strategy.legs[leg].symbol}'
                        rows, cols = table_.shape

                        if rows > MAX_ROWS:
                            rows = MAX_ROWS
                        else:
                            rows = -1

                        if cols > MAX_COLS:
                            cols = MAX_COLS
                        else:
                            cols = -1

                        if rows > 0 or cols > 0:
                            # compress the table rows and columns
                            table_ = u.compress_table(table_, rows, cols)

                        if val == 1:
                            print(u.delimeter(title, True) + '\n')
                            print(table_)

                        if val == 2:
                            self._show_chart(table_, title, charttype='chart')
                        elif val == 3:
                            self._show_chart(table_, title, charttype='contour')
                        elif val == 4:
                            self._show_chart(table_, title, charttype='surface')
            else:
                u.print_error('No tables calculated')
        else:
            u.print_error('Please first perform calculation')

    def show_analysis(self, val=0):
        if not self.dirty_analyze:
            table_ = self.strategy.analysis.table
            if table_ is not None:
                if val == 0:
                    val = u.input_integer('(1) Summary, (2) Table, (3) Chart, (4) Contour, (5) Surface, or (0) Cancel: ', 0, 5)
                if val > 0:
                    title = f'Analysis: {self.strategy.ticker} ({self.strategy.legs[0].symbol}) {str(self.strategy).title()}'
                    rows, cols = table_.shape

                    if rows > MAX_ROWS:
                        rows = MAX_ROWS
                    else:
                        rows = -1

                    if cols > MAX_COLS:
                        cols = MAX_COLS
                    else:
                        cols = -1

                    if rows > 0 or cols > 0:
                        table_ = u.compress_table(table_, rows, cols)

                    if val == 1:
                        print(u.delimeter(title, True))
                        print(self.strategy.analysis)
                    elif val == 2:
                        print(u.delimeter(title, True))
                        print(table_)
                    elif val == 3:
                        self._show_chart(table_, title, charttype='chart')
                    elif val == 4:
                        self._show_chart(table_, title, charttype='contour')
                    elif val == 5:
                        self._show_chart(table_, title, charttype='surface')
            else:
                u.print_error('No tables calculated')
        else:
            u.print_error('Please first perform analysis')

    def show_options(self):
        if len(self.strategy.legs) > 0:
            if len(self.strategy.legs) > 1:
                leg = u.input_integer('Enter Leg (0=all): ', 0, 2) - 1
            else:
                leg = 0

            if leg < 0:
                print(u.delimeter('Leg 1 Option Metrics', True))
            else:
                print(u.delimeter(f'Leg {leg+1} Option Metrics', True))
            if leg < 0:
                print(f'{self.strategy.legs[0].option}')
                print(u.delimeter('Leg 2 Option Metrics', True))
                print(f'{self.strategy.legs[1].option}')
            else:
                print(f'{self.strategy.legs[leg].option}')
        else:
            print('No option legs configured')

    def show_legs(self, leg=-1, delimeter=True):
        if delimeter:
            print(u.delimeter('Option Leg Values', True))

        if len(self.strategy.legs) < 1:
            print('No legs configured')
        elif leg < 0:
            for index in range(len(self.strategy.legs)):
                # Recursive call to output each leg
                self.show_legs(index, False)
        elif leg < len(self.strategy.legs):
            output = f'{leg+1}: {self.strategy.legs[leg]}'
            print(output)
        else:
            u.print_error('Invalid leg')

    def calculate(self):
        try:
            self.strategy.calculate()
            self.dirty_calculate = False
            return True
        except Exception as e:
            return False

    def analyze(self):
        errors = self.strategy.get_errors()
        if not errors:
            self.strategy.analyze()

            self.dirty_calculate = False
            self.dirty_analyze = False

            self.show_analysis(val=1)
        else:
            u.print_error(errors)

    def reset(self):
        self.strategy.reset()

    def select_symbol(self):
        valid = False
        vol = 0.0
        div = 0.0

        while not valid:
            ticker = input('Please enter symbol, or 0 to cancel: ').upper()
            if ticker != '0':
                valid = f.validate_ticker(ticker)
                if not valid:
                    u.print_error('Invalid ticker symbol. Try again or select "0" to cancel')
            else:
                break

        if valid:
            self.ticker = ticker
            self.dirty_calculate = True
            self.dirty_analyze = True

            self.chain = Chain(ticker)
            self.load_strategy(ticker, 'call', 'long', False)
            u.print_message('The initial strategy has been set to a long call')

    def select_strategy(self):
        menu_items = {
            '1': 'Call',
            '2': 'Put',
            '3': 'Vertical',
            '0': 'Done/Cancel',
        }

        # Select strategy
        strategy = ''
        modified = False
        while True:
            selection = u.menu(menu_items, 'Select Strategy', 0, 4)

            if selection == 1:
                direction = u.input_integer('Long (1), or short (2): ', 1, 2)
                direction = 'long' if direction == 1 else 'short'
                self.strategy = Call(self.strategy.ticker, 'call', direction)

                self.dirty_calculate = True
                self.dirty_analyze = True
                modified = True
                break

            if selection == 2:
                direction = u.input_integer('Long (1), or short (2): ', 1, 2)
                direction = 'long' if direction == 1 else 'short'
                self.strategy = Put(self.strategy.ticker, 'put', direction)

                self.dirty_calculate = True
                self.dirty_analyze = True
                modified = True
                break

            if selection == 3:
                product = u.input_integer('Call (1), or Put (2): ', 1, 2)
                product = 'call' if product == 1 else 'put'
                direction = u.input_integer('Debit (1), or credit (2): ', 1, 2)
                direction = 'long' if direction == 1 else 'short'

                self.strategy = Vertical(self.strategy.ticker, product, direction)

                self.dirty_calculate = True
                self.dirty_analyze = True
                modified = True
                break

            if selection == 0:
                break

            u.print_error('Unknown strategy selected')

        return modified

    def select_chain(self):
        contract = ''

        # Go directly to get expire date if not already entered
        if self.chain.expire is None:
            ret = self.select_chain_expiry()
            if ret:
                self.strategy.update_expiry(ret)
                if self.strategy.name != 'vertical':
                    # Go directly to choose option if only one leg in strategy
                    if self.strategy.legs[0].option.product == 'call':
                        contract = self.select_chain_option('call')
                    else:
                        contract = self.select_chain_option('put')

                    # Load the new contract
                    if contract:
                        self.strategy.legs[0].option.load_contract(contract)

        if not contract:
            while True:
                if self.chain.expire is not None:
                    expiry = self.chain.expire
                else:
                    expiry = 'None selected'

                if self.strategy.legs[0].option.product == 'call':
                    product = 'Call'
                else:
                    product = 'Put'

                menu_items = {
                    '1': f'Select Expiry Date ({expiry})',
                    '2': f'Select {product} Option',
                    '3': 'Done',
                }

                if self.strategy.name == 'vertical':
                    menu_items['2'] = f'Select {product} Options'
                    menu_items['2'] += f' '\
                        f'(L:${self.strategy.legs[0].option.strike:.2f}{self.strategy.legs[0].option.decorator}'\
                        f' S:${self.strategy.legs[1].option.strike:.2f}{self.strategy.legs[1].option.decorator})'
                else:
                    menu_items['2'] += f' (${self.strategy.legs[0].option.strike:.2f}{self.strategy.legs[0].option.decorator})'

                selection = u.menu(menu_items, 'Select Operation', 0, 3)

                ret = True
                if selection == 1:
                    if self.select_chain_expiry():
                        self.strategy.update_expiry(ret)

                elif selection == 2:
                    if self.chain.expire is not None:
                        if self.strategy.name == 'vertical':
                            leg = u.input_integer('Long leg (1), or short (2): ', 1, 2) - 1
                        else:
                            leg = 0

                        if self.strategy.legs[leg].option.product == 'call':
                            contract = self.select_chain_option('call')
                        else:
                            contract = self.select_chain_option('put')

                        if contract:
                            ret = self.strategy.legs[leg].option.load_contract(contract)
                        else:
                            u.print_error('No option selected')

                        if self.strategy.name != 'vertical':
                            break
                    else:
                        u.print_error('Please first select expiry date')
                elif selection == 3:
                    break
                elif selection == 0:
                    break

                if not ret:
                    u.print_error('Error loading option. Please try again')

        return contract

    def select_chain_expiry(self):
        expiry = self.chain.get_expiry()

        print('\nSelect Expiration')
        print('-------------------------')
        for index, exp in enumerate(expiry):
            print(f'{index+1})\t{exp}')

        select = u.input_integer('Select expiration date, or 0 to cancel: ', 0, index+1)
        if select > 0:
            self.chain.expire = expiry[select-1]
            expiry = datetime.datetime.strptime(self.chain.expire, '%Y-%m-%d')

            self.dirty_calculate = True
            self.dirty_analyze = True
        else:
            expiry = None

        return expiry

    def select_chain_option(self, product):
        options = None
        contract = ''
        if self.chain.expire is None:
            u.print_error('No expiry date delected')
        elif product == 'call':
            options = self.chain.get_chain('call')
        elif product == 'put':
            options = self.chain.get_chain('put')

        if options is not None:
            print('\nSelect option')
            print('-------------------------')
            for index, row in options.iterrows():
                chain = f'{index+1})\t'\
                    f'${row["strike"]:7.2f} '\
                    f'${row["lastPrice"]:7.2f} '\
                    f'ITM: {bool(row["inTheMoney"])}'
                print(chain)

            select = u.input_integer('Select option, or 0 to cancel: ', 0, index + 1)

            if select > 0:
                sel_row = options.iloc[select-1]
                contract = sel_row['contractSymbol']

                self.dirty_calculate = True
                self.dirty_analyze = True
        else:
            u.print_error('Invalid selection')

        return contract

    def select_settings(self):
        while True:
            menu_items = {
                '1': f'Pricing Method ({self.strategy.legs[0].pricing_method.title()})',
                '0': 'Done',
            }

            selection = u.menu(menu_items, 'Select Setting', 0, 1)

            if selection == 1:
                self.select_method()
            elif selection == 0:
                break

    def select_method(self):
        menu_items = {
            '1': 'Black-Scholes',
            '2': 'Monte Carlo',
            '0': 'Cancel',
        }

        modified = True
        while True:
            selection = u.menu(menu_items, 'Select Method', 0, 2)

            if selection == 1:
                self.strategy.set_pricing_method('black-scholes')
                self.dirty_calculate = True
                self.dirty_analyze = True
                break

            if selection == 2:
                self.strategy.set_pricing_method('monte-carlo')
                self.dirty_calculate = True
                self.dirty_analyze = True
                break

            if selection == 0:
                break

            u.print_error('Unknown method selected')

    def load_strategy(self, ticker, name, direction, analyze=True):
        modified = False

        try:
            if name.lower() == 'call':
                modified = True
                self.strategy = Call(ticker, 'call', direction)
                if analyze:
                    self.analyze()
            elif name.lower() == 'put':
                modified = True
                self.strategy = Put(ticker, 'put', direction)
                if analyze:
                    self.analyze()
            elif name.lower() == 'vertc':
                modified = True
                self.strategy = Vertical(ticker, 'call', direction)
                if analyze:
                    self.analyze()
            elif name.lower() == 'vertp':
                modified = True
                self.strategy = Vertical(ticker, 'put', direction)
                if analyze:
                    self.analyze()
            else:
                u.print_error('Unknown argument')

        except Exception as e:
            u.print_error(sys.exc_info()[1], True)
            return False

        return modified

    def _show_chart(self, table, title, charttype):
        if not isinstance(table, pd.DataFrame):
            raise AssertionError("'table' must be a Pandas DataFrame")

        if charttype == 'surface':
            dim = 3
        else:
            dim = 2

        # The plot
        fig = plt.figure()

        if dim == 3:
            ax = fig.add_subplot(111, projection='3d')
        else:
            ax = fig.add_subplot(111)

        plt.style.use('seaborn')
        plt.title(title)

        # X Axis
        ax.xaxis.tick_top()
        ax.set_xticks(range(len(table.columns)))
        ax.set_xticklabels(table.columns.tolist())
        ax.xaxis.set_major_locator(mticker.MultipleLocator(1))

        # Y Axis
        ax.yaxis.set_major_formatter('${x:.2f}')
        height = table.index[0] - table.index[-1]
        major, minor = u.calc_major_minor_ticks(height)
        if major > 0:
            ax.yaxis.set_major_locator(mticker.MultipleLocator(major))
        if minor > 0:
            ax.yaxis.set_minor_locator(mticker.MultipleLocator(minor))

        ax.set_xlabel('Date')
        if dim == 2:
            ax.set_ylabel('Value')
        else:
            ax.set_ylabel('Price')
            ax.set_zlabel('Value')

        # Color distributions
        min_ = min(table.min())
        max_ = max(table.max())
        if min_ < 0.0:
            norm = clrs.TwoSlopeNorm(0.0, vmin=min_, vmax=max_)
            cmap = clrs.LinearSegmentedColormap.from_list(name='analysis', colors =['red', 'lightgray', 'green'], N=15)
        else:
            norm=None
            cmap = clrs.LinearSegmentedColormap.from_list(name='value', colors =['lightgray', 'green'], N=15)

        # Data
        table.columns = range(len(table.columns))
        x = table.columns
        y = table.index
        X, Y = np.meshgrid(x, y)
        Z = table

        # Plot
        if charttype == 'chart':
            ax.scatter(X, Y, c=Z, norm=norm, marker='s', cmap=cmap)
        elif charttype == 'contour':
            ax.contourf(X, Y, Z, norm=norm, cmap=cmap)
        elif charttype == 'surface':
            ax.plot_surface(X, Y, Z, norm=norm, cmap=cmap)
        else:
            raise AssertionError('Bad chart type')

        breakeven = self.strategy.analysis.breakeven
        ax.axhline(breakeven, color='k', linestyle='-', linewidth=0.5)

        plt.show()

    def _menu(self, menu_items, header, minvalue, maxvalue):
        print(f'\n{header}')
        print('-----------------------------')

        option = menu_items.keys()
        for entry in option:
            print(f'{entry})\t{menu_items[entry]}')

        return u.input_integer('Please select: ', minvalue, maxvalue)


if __name__ == '__main__':
    import argparse

    # Create the top-level parser
    parser = argparse.ArgumentParser(description='Option Strategy Analyzer')
    subparser = parser.add_subparsers(help='Specify the desired command')

    parser.add_argument('-x', '--exit', help='Exit after running loaded strategy or script', action='store_true', required=False, default=False)

    # Create the parser for the "load" command
    parser_a = subparser.add_parser('load', help='Load a strategy')
    parser_a.add_argument('-t', '--ticker', help='Specify the ticker symbol', required=False, default='IBM')
    parser_a.add_argument('-s', '--strategy', help='Load and analyze strategy', required=False, choices=['call', 'put', 'vertc', 'vertp'], default=None)
    parser_a.add_argument('-d', '--direction', help='Specify the direction', required=False, choices=['long', 'short'], default='long')

    # Create the parser for the "execute" command
    parser_b = subparser.add_parser('execute', help='Execute a JSON command script')
    parser_b.add_argument('-f', '--script', help='Specify a script', required=False, default='script.json')

    command = vars(parser.parse_args())

    if 'strategy' in command.keys():
        Interface(ticker=command['ticker'], strategy='call', direction=command['direction'], autoload=command['strategy'], exit=command['exit'])
    elif 'script' in command.keys():
        Interface('FB', 'call', 'long', script=command['script'], exit=command['exit'])
    else:
        Interface('MSFT', 'call', 'long', exit=command['exit'])