import os, json
import logging
import datetime as dt

import matplotlib.pyplot as plt

from analysis.technical import Technical
from analysis.trend import SupportResistance
from data import store as store
from utils import utils as utils


logger = utils.get_logger(logging.WARNING)

class Interface:
    def __init__(self, ticker, script=''):
        self.technical = None

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
        elif store.is_symbol_valid(ticker.upper()):
            self.technical = Technical(ticker.upper(), None, 365)
            self.main_menu()
        else:
            self.main_menu()

    def main_menu(self):
        while True:
            menu_items = {
                '1': 'Change Symbol',
                '2': 'Technical Analysis',
                '3': 'Support & Resistance Chart',
                '4': 'Plot All',
                '0': 'Exit'
            }

            if self.technical is not None:
                menu_items['1'] = f'Change Symbol ({self.technical.ticker})'

            selection = utils.menu(menu_items, 'Select Operation', 0, 4)

            if selection == 1:
                self.select_symbol()
            elif selection == 2:
                self.select_technical()
            elif selection == 3:
                self.get_trend_parameters()
            elif selection == 4:
                self.plot_all()
            elif selection == 0:
                break

    def select_symbol(self):
        valid = False

        while not valid:
            ticker = input('Please enter symbol, or 0 to cancel: ').upper()
            if ticker != '0':
                valid = store.is_symbol_valid(ticker)
                if valid:
                    self.technical = Technical(ticker, None, 365)
                else:
                    utils.print_error('Invalid ticker symbol. Try again or select "0" to cancel')
            else:
                break

    def select_technical(self):
        if self.technical is not None:
            while True:
                menu_items = {
                    '1': 'EMA',
                    '2': 'RSI',
                    '3': 'VWAP',
                    '4': 'MACD',
                    '5': 'Bollinger Bands',
                    '0': 'Done',
                }

                selection = utils.menu(menu_items, 'Select Indicator', 0, 5)

                if selection == 1:
                    interval = utils.input_integer('Enter interval: ', 5, 200)
                    df = self.technical.calc_ema(interval)
                    utils.print_message(f'EMA {interval}')
                    print(f'Yesterday: {df.iloc[-1]:.2f}')
                    self.plot(df, f'EMA {interval}')
                elif selection == 2:
                    df = self.technical.calc_rsi()
                    utils.print_message('RSI')
                    print(f'Yesterday: {df.iloc[-1]:.2f}')
                elif selection == 3:
                    df = self.technical.calc_vwap()
                    utils.print_message('VWAP')
                    print(f'Yesterday: {df.iloc[-1]:.2f}')
                elif selection == 4:
                    df = self.technical.calc_macd()
                    utils.print_message('MACD')
                    print(f'Diff: {df.iloc[-1]["Diff"]:.2f}')
                    print(f'MACD: {df.iloc[-1]["MACD"]:.2f}')
                    print(f'Sig:  {df.iloc[-1]["Signal"]:.2f}')
                elif selection == 5:
                    df = self.technical.calc_bb()
                    utils.print_message('Bollinger Band')
                    print(f'High: {df.iloc[-1]["High"]:.2f}')
                    print(f'Mid:  {df.iloc[-1]["Mid"]:.2f}')
                    print(f'Low:  {df.iloc[-1]["Low"]:.2f}')
                elif selection == 0:
                    break
        else:
            utils.print_error('Please forst select symbol')

    def get_trend_parameters(self):
        if self.technical is not None:
            days = 1000
            filename = ''
            show = True

            while True:
                name = filename if filename else 'none'
                menu_items = {
                    '1': f'Number of Days ({days})',
                    '2': f'Plot File Name ({name})',
                    '3': f'Show Window ({show})',
                    '4': 'Analyze',
                    '0': 'Cancel'
                }

                selection = utils.menu(menu_items, 'Select option', 0, 4)

                if selection == 1:
                    days = utils.input_integer('Enter number of days (0=max): ', 0, 9999)

                if selection == 2:
                    filename = input('Enter filename: ')

                if selection == 3:
                    show = True if utils.input_integer('Show Window? (1=Yes, 0=No): ', 0, 1) == 1 else False

                if selection == 4:
                    sr = SupportResistance(self.technical.ticker, days=days)
                    sr.calculate()

                    sup = sr.get_support()
                    utils.print_message(f'{sr.ticker} Support & Resistance Levels (${sr.price:.2f})')
                    for line in sup:
                        print(f'Support:    ${line.end_point:.2f} ({line.get_score():.2f})')

                    res = sr.get_resistance()
                    for line in res:
                        print(f'Resistance: ${line.end_point:.2f} ({line.get_score():.2f})')

                    sr.plot(filename=filename, show=show)
                    break

                if selection == 0:
                    break
        else:
            utils.print_error('Please forst select symbol')


    def plot_all(self):
        if self.technical is not None:
            df1 = self.technical.calc_ema(21)
            df2 = self.technical.calc_rsi()
            df3 = self.technical.calc_vwap()
            df4 = self.technical.calc_macd()
            df5 = self.technical.calc_bb()
            df1.plot(label='EMA')
            df2.plot(label='RSI')
            df3.plot(label='VWAP')
            df4.plot(label='MACD')
            df5.plot(label='BB')
            plt.legend()
            plt.show()
        else:
            utils.print_error('Please forst select symbol')

    def plot(self, df, title=''):
        if df is not None:
            plt.style.use('seaborn-whitegrid')
            plt.grid()
            plt.margins(x=0.1)
            plt.legend()
            if title:
                plt.title(title)
            df.plot()
            plt.show()


if __name__ == '__main__':
    import argparse

    # Create the top-level parser
    parser = argparse.ArgumentParser(description='Technical Analysis')
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
        Interface(command['ticker'])
    else:
        Interface('AAPL')
