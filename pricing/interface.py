''' TODO '''
import datetime

import pandas as pd

from strategy import Strategy
import utils


class Interface():
    '''TODO'''

    def __init__(self):
        self.strategy = Strategy()

        date = datetime.datetime(2021, 2, 12)
        self.leg = {'quantity': 1, 'call_put': 'call', 'long_short': 'long', 'strike': 130, 'expiry': date}

        pd.options.display.float_format = '{:,.2f}'.format

    def main_menu(self):
        '''Displays opening menu'''

        menu_items = {
            '1': 'Specify Symbol',
            '2': 'Specify Strategy',
            '3': 'Configure Leg',
            '4': 'Calculate',
            '5': 'Plot Value',
            '6': 'Plot Profit',
            '7': 'Exit'
        }

        while True:
            print('\nSelect Option')
            print('-------------------------')

            option = menu_items.keys()
            for entry in option:
                print(f'{entry})\t{menu_items[entry]}')

            selection = input('Please select: ')

            if selection == '1':
                self.enter_symbol()
            elif selection == '2':
                self.enter_strategy()
            elif selection == '3':
                self.enter_leg()
                self.strategy.write_leg(0)
            elif selection == '4':
                self.calculate()
                self.write_all()
            elif selection == '5':
                self.plot_value()
            elif selection == '6':
                self.plot_profit()
            elif selection == '7':
                break
            else:
                print('Unknown operation selected')

    def calculate(self):
        '''TODO'''
        self.strategy.calculate_leg()

    def reset(self):
        '''TODO'''
        self.strategy.reset()

    def enter_symbol(self):
        '''TODO'''
        ticker = input('Please enter symbol: ').upper()
        vol = -1.0
        div = 0.0

        menu_items = {
            '1': 'Specify Volitility',
            '2': 'Specify Dividend',
            '3': 'Back'
        }

        while True:
            print('\nSelect Option')
            print('-------------------------')

            option = menu_items.keys()
            for entry in option:
                print(f'{entry})\t{menu_items[entry]}')

            selection = input('Please select: ')

            if selection == '1':
                pass
            elif selection == '2':
                pass
            elif selection == '3':
                break
            else:
                print('Unknown operation selected')

        self.strategy.set_symbol(ticker, vol, div)
        self.write_all()

    def enter_strategy(self):
        '''TODO'''
        self.write_all()

    def enter_leg(self):
        '''TODO'''

        menu_items = {
            '1': 'Quantity',
            '2': 'Call/Put',
            '3': 'Long/Short',
            '4': 'Strike',
            '5': 'Expiration',
            '6': 'Add Leg',
            '7': 'Cancel',
        }

        while True:
            self.strategy.write_leg(0)
            print('\nSpecify Leg')
            print('-------------------------')

            option = menu_items.keys()
            for entry in option:
                print(f'{entry})\t{menu_items[entry]}')

            selection = input('Please select: ')

            if selection == '1':
                choice = input('Enter Quantity: ')
                if choice.isnumeric():
                    self.leg['quantity'] = int(choice)
                else:
                    print('Invalid option')
            elif selection == '2':
                choice = input('Call (c) or Put (p): ')
                if 'c' in choice:
                    self.leg['call_put'] = 'call'
                elif 'p' in choice:
                    self.leg['call_put'] = 'put'
                else:
                    print('Invalid option')
            elif selection == '3':
                choice = input('Long (l) or Short (s): ')
                if 'l' in choice:
                    self.leg['long_short'] = 'long'
                elif 's' in choice:
                    self.leg['long_short'] = 'short'
                else:
                    print('Invalid option')
            elif selection == '4':
                choice = input('Enter Strike: ')
                if choice.isnumeric():
                    self.leg['strike'] = float(choice)
                else:
                    print('Invalid option')
            elif selection == '5':
                pass
            elif selection == '6':
                self.strategy.add_leg(self.leg['quantity'], self.leg['call_put'],
                                      self.leg['long_short'], self.leg['strike'], self.leg['expiry'])
                break
            elif selection == '7':
                break
            else:
                print('Unknown operation selected')


    def write_all(self):
        '''TODO'''
        print(utils.delimeter('Configuration', True))
        output = \
            f'Strategy:{self.strategy.strategy}, Method:{self.strategy.pricing_method}'
        print(output)
        output = \
            f'{self.leg["quantity"]} '\
            f'{self.strategy.symbol["ticker"]} '\
            f'{str(self.leg["expiry"])[:10]} '\
            f'{self.leg["long_short"]} '\
            f'{self.leg["call_put"]} '\
            f'@${self.leg["strike"]:.2f} = '\
            f'${self.strategy.legs[0].price:.2f}\n'
        print(output)

    def plot_value(self):
        '''TODO'''
        self.write_all()
        print(utils.delimeter('Value', True))
        print(self.strategy.table_value)

    def plot_profit(self):
        '''TODO'''
        self.write_all()
        print(utils.delimeter('Profit', True))
        print(self.strategy.table_profit)

    def _validate(self):
        '''TODO'''
        return True


if __name__ == '__main__':
    ui = Interface()
    ui.main_menu()
