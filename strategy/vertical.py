'''TODO'''

import datetime
import logging

import pandas as pd

from strategy.strategy import Strategy


class Vertical(Strategy):
    '''TODO'''
    def __init__(self, symbol=''):
        super().__init__(symbol)

        self.name = 'vertical'
        self.add_leg(1, 'call', 'long', 100.0)
        self.add_leg(1, 'call', 'short', 105.0)

        if symbol:
            self.legs[0].calculate()
            self.legs[1].calculate()


    def __str__(self):
        return f'{self.name} {self.credit_debit} spread'


    def analyze(self):
        dframe = None
        legs = 0

        if len(self.legs) <= 0:
            pass
        else:
            legs = 2
            self.legs[0].calculate()
            self.legs[1].calculate()

            if self.legs[0].long_short == 'long':
                if self.legs[0].price > self.legs[1].price:
                    self.credit_debit = 'debit'
                else:
                    self.credit_debit = 'credit'

                dframe = self.legs[0].table - self.legs[1].table
            else:
                if self.legs[0].price > self.legs[1].price:
                    self.credit_debit = 'credit'
                else:
                    self.credit_debit = 'debit'

                dframe = self.legs[1].table - self.legs[0].table

            self.analysis.table = dframe

        return legs

    def _calc_price_min_max_step(self):
        if len(self.legs) <= 0:
            min_ = max_ = step_ = 0
        else:
            min_ = int(min([self.legs[0].strike, self.legs[1].strike])) - 10
            max_ = int(max([self.legs[0].strike, self.legs[1].strike])) + 11
            step_ = 1

        return min_, max_, step_
