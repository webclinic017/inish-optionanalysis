import sys
import time
import math
import threading
import datetime as dt
import logging

import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as clrs
import matplotlib.ticker as mticker
from tabulate import tabulate

import strategies as s
from strategies.strategy import Strategy
from strategies.vertical import Vertical
from strategies.call import Call
from strategies.put import Put
from strategies.iron_condor import IronCondor
from strategies.iron_butterfly import IronButterfly
from data import store
from utils import math as m
from utils import ui, logger


logger.get_logger(logging.WARNING, logfile='')


class Interface():
    def __init__(self,
        *,
        ticker: str,
        strategy: str,
        product: str,
        direction: str,
        strike: float = -1.0,
        width1: int = 0,
        width2: int = 0,
        quantity: int = 1,
        expiry: str = '',
        load_contracts: bool = False,
        analyze: bool = False,
        exit: bool = False):

        self.ticker = ticker.upper()
        self.strategy: Strategy = None
        self.product = product
        self.direction = direction
        self.strike = strike
        self.width1 = width1
        self.width2 = width2
        self.quantity = quantity
        self.expiry = expiry
        self.load_contracts = load_contracts

        self.dirty_analyze = True
        self.task: threading.Thread = None

        pd.options.display.float_format = '{:,.2f}'.format

        # Set self.strike to closest ITM if strike < 0.0
        if direction == 'long':
            self.strike = strike if strike > 0.0 else float(math.floor(store.get_last_price(self.ticker)))
            if self.strike <= 0.0:
                self.strike = 0.50
        else:
            self.strike = strike if strike > 0.0 else float(math.ceil(store.get_last_price(self.ticker)))

        if not store.is_live_connection():
            ui.print_error('Internet connection required')
        elif not store.is_ticker(ticker):
            ui.print_error('Invalid ticker specified')
        elif strategy not in s.STRATEGIES:
            ui.print_error('Invalid strategy specified')
        elif direction not in s.DIRECTIONS:
            ui.print_error('Invalid direction specified')
        elif product not in s.PRODUCTS:
            ui.print_error('Invalid product specified')
        elif width1 < 0:
            ui.print_error('Invalid width specified')
        elif quantity < 1:
            ui.print_error('Invalid quantity specified')
        elif strategy == 'vert' and width1 < 1:
            ui.print_error('Invalid width specified')
        elif strategy == 'ic' and (width1 < 1 or width2 < 1):
            ui.print_error('Invalid width specified')
        elif strategy == 'ib' and width1 < 1:
            ui.print_error('Invalid width specified')
        elif self.load_strategy(self.ticker, strategy, self.product, self.direction, self.strike, self.width1, self.width2, self.quantity, self.expiry, load_contracts, analyze or exit):
            if not exit:
                self.main_menu()
        else:
            ui.print_error('Problem loading strategy')

    def main_menu(self) -> None:
        while True:
            menu_items = {
                '1': f'Change Symbol ({self.strategy.ticker})',
                '2': f'Change Strategy ({self.strategy})',
                '3': 'Select Option',
                '4': 'View Option Details',
                '5': 'View Value',
                '6': 'Analyze Stategy',
                '7': 'View Analysis',
                '8': 'Settings',
                '0': 'Exit'
            }

            loaded = '' if self.strategy.legs[0].option.last_price > 0 else '*'
            expire = f'{self.strategy.legs[0].option.expiry:%Y-%m-%d}'

            if self.strategy.name == s.STRATEGIES_BROAD[2]: # Vertical
                menu_items['3'] += f's ({expire}, '\
                    f'L:${self.strategy.legs[0].option.strike:.2f}{loaded}, '\
                    f'S:${self.strategy.legs[1].option.strike:.2f}{loaded})'
            elif self.strategy.name == s.STRATEGIES_BROAD[3]: # Iron Condor
                menu_items['3'] += f's ({expire}, '\
                    f'${self.strategy.legs[0].option.strike:.2f}{loaded}, '\
                    f'${self.strategy.legs[1].option.strike:.2f}{loaded}, '\
                    f'${self.strategy.legs[2].option.strike:.2f}{loaded}, '\
                    f'${self.strategy.legs[3].option.strike:.2f}{loaded})'
            else: # Call or Put
                menu_items['3'] += f' ({expire}, ${self.strategy.legs[0].option.strike:.2f}{loaded})'

            if self.dirty_analyze:
                menu_items['6'] += ' *'

            selection = ui.menu(menu_items, 'Select Operation', 0, len(menu_items)-1)

            if selection == 1:
                if self.select_ticker():
                    self.analyze()
            elif selection == 2:
                if self.select_strategy():
                    self.analyze()
            elif selection == 3:
                if self.select_chain():
                    self.analyze()
            elif selection == 4:
                self.show_options()
            elif selection == 5:
                self.show_value()
            elif selection == 6:
                self.analyze()
            elif selection == 7:
                self.show_analysis()
            elif selection == 8:
                self.select_settings()
            elif selection == 0:
                break

    def load_strategy(self,
            ticker: str,
            strategy: str,
            product: str,
            direction: str,
            strike: float,
            width1: int,
            width2: int,
            quantity: int,
            expiry: str,
            load_contracts: bool = False,
            analyze: bool = False) -> bool:

        modified = True

        if not store.is_ticker(ticker):
            raise ValueError('Invalid ticker')
        if strategy not in s.STRATEGIES:
            raise ValueError('Invalid strategy')
        if direction not in s.DIRECTIONS:
            raise ValueError('Invalid direction')
        if strike < 0.0:
            raise ValueError('Invalid strike')
        if quantity < 1:
            raise ValueError('Invalid quantity')
        if strategy == 'vert' and width1 < 1:
            raise ValueError('Invalid width specified')

        self.ticker = ticker.upper()
        self.direction = direction
        self.strike = strike
        self.quantity = quantity
        self.width1 = width1

        expiry_dt = dt.datetime.strptime(expiry, '%Y-%m-%d') if expiry else None

        try:
            if strategy.lower() == 'call':
                self.width1 = 0
                self.strategy = Call(self.ticker, 'call', direction, strike, 0, 0, quantity=quantity, expiry=expiry_dt, volatility=-1.0, load_contracts=load_contracts)
            elif strategy.lower() == 'put':
                self.width1 = 0
                self.strategy = Put(self.ticker, 'put', direction, strike, 0, 0, quantity=quantity, expiry=expiry_dt, volatility=-1.0, load_contracts=load_contracts)
            elif strategy.lower() == 'vert':
                self.strategy = Vertical(self.ticker, product, direction, strike, width1, 0, quantity=quantity, expiry=expiry_dt, volatility=-1.0, load_contracts=load_contracts)
            elif strategy.lower() == 'ic':
                self.strategy = IronCondor(self.ticker, 'hybrid', direction, strike, width1, width2, quantity=quantity, expiry=expiry_dt, volatility=-1.0, load_contracts=load_contracts)
            elif strategy.lower() == 'ib':
                self.strategy = IronButterfly(self.ticker, 'hybrid', direction, strike, width1, 0, quantity=quantity, expiry=expiry_dt, volatility=-1.0, load_contracts=load_contracts)
            else:
                modified = False
                ui.print_error('Unknown argument')
        except Exception as e:
            ui.print_error(f'{__name__}: {str(sys.exc_info()[1])}')
            modified = False

        if modified:
            self.dirty_analyze = True

            if analyze:
                modified = self.analyze()

        return modified

    def analyze(self) -> bool:
        valid = self.strategy.validate()
        if valid:
            self.task = threading.Thread(target=self.strategy.analyze)
            self.task.start()

            # Show thread progress. Blocking while thread is active
            self.show_progress()

            self.dirty_analyze = False

            self.show_analysis(style=1)
            self.show_analysis(style=2)
        else:
            ui.print_error(self.strategy.error)

        return valid

    def reset(self) -> None:
        self.strategy.reset()

    def show_value(self, style: int = 0) -> None:
        if not self.dirty_analyze:
            if len(self.strategy.legs) > 1:
                leg = ui.input_integer('Enter Leg: ', 1, len(self.strategy.legs)) - 1
            else:
                leg = 0

            value = self.strategy.legs[leg].value_table
            if value is not None:
                if style == 0:
                    style = ui.input_integer('(1) Table, (2) Chart, (3) Contour, (4) Surface, or (0) Cancel: ', 0, 4)
                if style > 0:
                    title = f'{self.strategy.legs[leg]}'
                    rows, cols = value.shape

                    if rows > m.VALUETABLE_ROWS:
                        rows = m.VALUETABLE_ROWS
                    else:
                        rows = -1

                    if cols > m.VALUETABLE_COLS:
                        cols = m.VALUETABLE_COLS
                    else:
                        cols = -1

                    if rows > 0 or cols > 0:
                        value = m.compress_table(value, rows, cols)

                    if style == 1:
                        ui.print_message(title, 2)
                        print(value)
                    elif style == 2:
                        self._show_chart(value, title, charttype='chart')
                    elif style == 3:
                        self._show_chart(value, title, charttype='contour')
                    elif style == 4:
                        self._show_chart(value, title, charttype='surface')
            else:
                ui.print_error('No tables calculated')
        else:
            ui.print_error('Please first perform calculation')

    def show_analysis(self, style: int = 0) -> None:
        if not self.dirty_analyze:
            analysis = self.strategy.analysis.table
            if analysis is not None:
                if style == 0:
                    style = ui.input_integer('(1) Summary, (2) Table, (3) Chart, (4) Contour, (5) Surface, or (0) Cancel: ', 0, 5)

                if style > 0:
                    title = f'{self.strategy.name.title()}: {self.strategy.ticker} (${self.strike:.2f})'

                    rows, cols = analysis.shape
                    if rows > m.VALUETABLE_ROWS:
                        rows = m.VALUETABLE_ROWS
                    else:
                        rows = -1

                    if cols > m.VALUETABLE_COLS:
                        cols = m.VALUETABLE_COLS
                    else:
                        cols = -1

                    if rows > 0 or cols > 0:
                        analysis = m.compress_table(analysis, rows, cols)

                    if style == 1:
                        ui.print_message(title, pre_creturn=2)
                        print(self.strategy.analysis)
                        if self.strategy.legs[0].option.contract:
                            ui.print_message('Option Contracts', pre_creturn=0)
                            for leg in self.strategy.legs:
                                print(f'{leg.option.contract}')

                        self.show_legs()
                    elif style == 2:
                        ui.print_message(title, post_creturn=1)
                        print(tabulate(analysis, headers=analysis.columns, tablefmt='simple', floatfmt='.2f'))
                    elif style == 3:
                        self._show_chart(analysis, title, charttype='chart')
                    elif style == 4:
                        self._show_chart(analysis, title, charttype='contour')
                    elif style == 5:
                        self._show_chart(analysis, title, charttype='surface')
            else:
                ui.print_error('No tables calculated')
        else:
            ui.print_error('Please first perform analysis')

    def show_options(self) -> None:
        if len(self.strategy.legs) > 0:
            if len(self.strategy.legs) > 1:
                leg = ui.input_integer('Enter Leg (0=all): ', 0, 2) - 1
            else:
                leg = 0

            if leg < 0:
                ui.print_message('Leg 1 Option Metrics')
            else:
                ui.print_message(f'Leg {leg+1} Option Metrics')

            if leg < 0:
                print(f'{self.strategy.legs[0].option}')
                ui.print_message('Leg 2 Option Metrics')
                print(f'{self.strategy.legs[1].option}')
            else:
                print(f'{self.strategy.legs[leg].option}')
        else:
            print('No option legs configured')

    def show_legs(self, leg: int = -1, delimeter: bool = True) -> None:
        if delimeter:
            ui.print_message('Option Legs')

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
            ui.print_error('Invalid leg')

    def select_ticker(self) -> bool:
        valid = False
        modified = False

        while not valid:
            ticker = input('Please enter symbol, or 0 to cancel: ').upper()
            if ticker != '0':
                valid = store.is_ticker(ticker)
                if not valid:
                    ui.print_error('Invalid ticker symbol. Try again or select "0" to cancel')
            else:
                break

        if valid:
            self.ticker = ticker
            self.dirty_analyze = True
            modified = True

            self.load_strategy(ticker, 'call', 'long', 1, analyze=True)
            ui.print_message('The strategy has been reset to a long call', False)

        return modified

    def select_strategy(self) -> bool:
        menu_items = {
            '1': 'Call',
            '2': 'Put',
            '3': 'Vertical',
            '4': 'Iron Condor',
            '0': 'Done/Cancel',
        }

        modified = True
        selection = ui.menu(menu_items, 'Select Strategy', 0, len(menu_items)-1)

        self.width1 = 0
        self.width2 = 0
        price = store.get_current_price(self.strategy.ticker)

        if selection == 1:
            d = ui.input_integer('(1) Long, or (2) Short: ', 1, 2)
            direction = 'long' if d == 1 else 'short'
            self.strike = ui.input_float_range(f'Enter strike ({price:.2f}): ', price, 20.0)
            self.load_strategy(self.strategy.ticker, 'call', 'call', direction, self.strike, 0, 0, self.quantity)
        elif selection == 2:
            d = ui.input_integer('(1) Long, or (2) Short: ', 1, 2)
            direction = 'long' if d == 1 else 'short'
            self.strike = ui.input_float_range(f'Enter strike ({price:.2f}): ', price, 20.0)
            self.load_strategy(self.strategy.ticker, 'put', 'put', direction, self.strike, 0, 0, self.quantity)
        elif selection == 3:
            p = ui.input_integer('(1) Call, or (2) Put: ', 1, 2)
            product = 'call' if p == 1 else 'put'
            d = ui.input_integer('(1) Debit, or (2) Credit: ', 1, 2)
            direction = 'long' if d == 1 else 'short'
            self.strike = ui.input_float_range(f'Enter strike ({price:.2f}): ', price, 20.0)
            self.width1 = self.width1 if self.width1 > 0 else 1
            self.load_strategy(self.strategy.ticker, 'vert', product, direction, self.strike, self.width1, 0, self.quantity)
        elif selection == 4:
            d = ui.input_integer('(1) Debit, or (2) Credit: ', 1, 2)
            direction = 'long' if d == 1 else 'short'
            self.strike = ui.input_float_range(f'Enter strike ({price:.2f}): ', price, 20.0)
            self.width1 = self.width1 if self.width1 > 0 else 1
            self.width2 = self.width2 if self.width2 > 0 else 1
            self.load_strategy(self.strategy.ticker, 'ic', 'hybrid', direction, self.strike, self.width1, self.width2, self.quantity)
        else:
            modified = False

        return modified

    def select_chain(self) -> list[str]:
        contracts = []

        # Go directly to get expire date if not already entered
        if not self.strategy.chain.expire:
            exp = self.select_chain_expiry()
            self.strategy.update_expiry(exp)
            if self.strategy.name != 'vertical':
                # Go directly to choose option if only one leg in strategy
                if self.strategy.legs[0].option.product == 'call':
                    contracts = self.select_chain_options('call')
                else:
                    contracts = self.select_chain_options('put')

                if contracts:
                    self.strategy.legs[0].option.load_contract(contracts[0])
                    print()

        if not contracts:
            done = False
            while not done:
                expiry = self.strategy.chain.expire if self.strategy.chain.expire else 'None selected'
                success = True

                menu_items = {
                    '1': f'Select Expiry Date ({expiry})',
                    '2': f'Quantity ({self.quantity})',
                    '3': f'Width ({self.width1})',
                    '4': f'Select Option',
                    '0': 'Done'
                }

                loaded = '' if self.strategy.legs[0].option.last_price > 0 else '*'

                if self.strategy.name == 'vertical':
                    menu_items['4'] += f's '\
                        f'(L:${self.strategy.legs[0].option.strike:.2f}{loaded}'\
                        f' S:${self.strategy.legs[1].option.strike:.2f}{loaded})'
                else:
                    menu_items['4'] += f' (${self.strategy.legs[0].option.strike:.2f}{loaded})'

                selection = ui.menu(menu_items, 'Select Operation', 0, len(menu_items)-1)

                if selection == 1:
                    exp = self.select_chain_expiry()
                    self.strategy.update_expiry(exp)
                elif selection == 2:
                    self.quantity = ui.input_integer('Enter quantity (1 - 10): ', 1, 10)
                elif selection == 3:
                    self.width1 = ui.input_integer('Enter width (1 - 5): ', 1, 5)
                elif selection == 4:
                    if self.strategy.chain.expire:
                        leg = 0
                        if self.strategy.legs[leg].option.product == 'call':
                            contracts = self.select_chain_options('call')
                        else:
                            contracts = self.select_chain_options('put')

                        if contracts:
                            for leg, contract in enumerate(contracts):
                                success = self.strategy.legs[leg].option.load_contract(contract)
                            done = True
                    else:
                        ui.print_error('Please first select expiry date')
                elif selection == 0:
                    done = True

                if not success:
                    ui.print_error('Error loading option. Please try again')

        return contracts

    def select_chain_expiry(self) -> dt.datetime:
        expiry = m.third_friday()
        dates = self.strategy.chain.get_expiry()

        menu_items = {}
        for i, exp in enumerate(dates):
            menu_items[f'{i+1}'] = f'{exp}'

        select = ui.menu(menu_items, 'Select expiration date, or 0 to cancel: ', 0, i+1)
        if select > 0:
            self.strategy.chain.expire = dates[select-1]
            expiry = dt.datetime.strptime(self.strategy.chain.expire, '%Y-%m-%d')

            self.dirty_analyze = True

        return expiry

    def select_chain_options(self, product: str) -> list[str]:
        options = None
        contracts = []
        if not self.strategy.chain.expire:
            ui.print_error('No expiry date delected')
        elif product == 'call':
            options = self.strategy.chain.get_chain('call')
        elif product == 'put':
            options = self.strategy.chain.get_chain('put')

        if options is not None:
            menu_items = {}
            for i, row in enumerate(options.itertuples()):
                itm = 'ITM' if bool(row.inTheMoney) else 'OTM'
                menu_items[f'{i+1}'] = f'${row.strike:7.2f} ${row.lastPrice:6.2f} {itm}'

            prompt = 'Select long option, or 0 to cancel: ' if self.strategy.name == 'vertical' else 'Select option, or 0 to cancel: '
            select = ui.menu(menu_items, prompt, 0, i+1)
            if select > 0:
                select -= 1
                sel_row = options.iloc[select]
                contracts = [sel_row['contractSymbol']]  # First contract

                if self.width1 > 0:
                    if product == 'call':
                        if self.strategy.direction == 'long':
                            sel_row = options.iloc[select+self.width1] if (select+self.width1) < options.shape[0] else None
                        else:
                            sel_row = options.iloc[select-self.width1] if (select-self.width1) >= 0 else None
                    elif self.strategy.direction == 'long':
                        sel_row = options.iloc[select-self.width1] if (select-self.width1) >= 0 else None
                    else:
                        sel_row = options.iloc[select+self.width1] if (select+self.width1) < options.shape[0] else None

                    if sel_row is not None:
                        contracts += [sel_row['contractSymbol']]  # Second contract
                    else:
                        contracts = []

                self.dirty_analyze = True
        else:
            ui.print_error('Invalid selection')

        return contracts

    def select_settings(self) -> None:
        while True:
            menu_items = {
                '1': f'Pricing Method ({self.strategy.legs[0].pricing_method.title()})',
                '0': 'Done',
            }

            selection = ui.menu(menu_items, 'Select Setting', 0, len(menu_items)-1)

            if selection == 1:
                self.select_method()
            elif selection == 0:
                break

    def select_method(self) -> None:
        menu_items = {
            '1': 'Black-Scholes',
            '2': 'Monte Carlo',
            '0': 'Cancel',
        }

        modified = True
        while True:
            selection = ui.menu(menu_items, 'Select Method', 0, len(menu_items)-1)

            if selection == 1:
                self.strategy.set_pricing_method('black-scholes')
                self.dirty_analyze = True
                break

            if selection == 2:
                self.strategy.set_pricing_method('monte-carlo')
                self.dirty_analyze = True
                break

            if selection == 0:
                break

            ui.print_error('Unknown method selected')

    def show_progress(self) -> None:
        ui.progress_bar(0, 0, prefix='Analyzing', suffix=self.ticker, reset=True)

        while self.task.is_alive():
            time.sleep(0.20)
            ui.progress_bar(0, 0, prefix='Analyzing', suffix=self.ticker)

    def _show_chart(self, table: str, title: str, charttype: str) -> None:
        if not isinstance(table, pd.DataFrame):
            raise ValueError("'table' must be a Pandas DataFrame")

        if charttype == 'surface':
            dim = 3
        else:
            dim = 2

        fig = plt.figure(figsize=(8, 8))

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
        major, minor = self._calculate_major_minor_ticks(height)
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
        if min_ < 0.0 and max_ > 0.0:
            norm = clrs.TwoSlopeNorm(0.0, vmin=min_, vmax=max_)
            cmap = clrs.LinearSegmentedColormap.from_list(name='analysis', colors=['red', 'lightgray', 'green'], N=15)
        elif min_ >= 0.0:
            norm = None
            cmap = clrs.LinearSegmentedColormap.from_list(name='value', colors=['lightgray', 'green'], N=15)
        elif max_ <= 0.0:
            norm = None
            cmap = clrs.LinearSegmentedColormap.from_list(name='value', colors=['red', 'lightgray'], N=15)
        else:
            norm = None
            cmap = clrs.LinearSegmentedColormap.from_list(name='value', colors=['lightgray', 'gray'], N=15)

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
            raise ValueError('Bad chart type')

        for breakeven in self.strategy.analysis.breakeven:
            ax.axhline(breakeven, color='k', linestyle='-', linewidth=0.5)

        plt.show()

    @staticmethod
    def _calculate_major_minor_ticks(width: int) -> tuple[float, float]:
        if width <= 0.0:
            major = 0.0
            minor = 0.0
        elif width > 1000:
            major = 100.0
            minor = 20.0
        elif width > 500:
            major = 50.0
            minor = 10.0
        elif width > 100:
            major = 10.0
            minor = 2.0
        elif width > 40:
            major = 5.0
            minor = 1.0
        elif width > 20:
            major = 2.0
            minor = 0.0
        elif width > 10:
            major = 1.0
            minor = 0.0
        elif width > 1:
            major = 0.5
            minor = 0.0
        else:
            major = 0.1
            minor = 0.0

        return major, minor


def main():
    parser = argparse.ArgumentParser(description='Option Strategy Analyzer')
    parser.add_argument('-t', '--ticker', help='Specify the ticker symbol', required=False, default='AAPL')
    parser.add_argument('-s', '--strategy', help='Load and analyze strategy', required=False, choices=['call', 'put', 'vert', 'ic', 'ib'], default='call')
    parser.add_argument('-d', '--direction', help='Specify the direction', required=False, choices=['long', 'short'], default='long')
    parser.add_argument('-p', '--product', help='Specify the product', required=False, choices=['call', 'put'], default='call')
    parser.add_argument('-k', '--strike', help='Specify the strike price', required=False, default='-1.0')
    parser.add_argument('-w1', '--width1', help='Specify the inner width', required=False, default='1')
    parser.add_argument('-w2', '--width2', help='Specify the outer width', required=False, default='1')
    parser.add_argument('-q', '--quantity', help='Specify the quantity', required=False, default='1')
    parser.add_argument('-e', '--expiry', help='Specify the expiry date (ex: "2022-03-29")', required=False, default='')
    parser.add_argument('-f', '--default', help='Load the default options', required=False, action='store_true')
    parser.add_argument('-a', '--analyze', help='Analyze the strategy', required=False, action='store_true')
    parser.add_argument('-x', '--exit', help='Run and exit', required=False, action='store_true')

    command = vars(parser.parse_args())
    Interface(ticker=command['ticker'], strategy=command['strategy'], product=command['product'], direction=command['direction'],
        width1=int(command['width1']), width2=int(command['width2']), quantity=int(command['quantity']), load_contracts=command['default'],
        expiry=command['expiry'], analyze=command['analyze'], exit=command['exit'], strike=float(command['strike']))


if __name__ == '__main__':
    main()
