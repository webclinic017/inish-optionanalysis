import pandas as pd

from base import Threaded
import strategies as s
from strategies.strategy import Strategy
from utils import ui
from utils import math as m


_logger = ui.get_logger()
DEFAULT_WIDTH = 2.0


class Vertical(Strategy):
    def __init__(self, ticker: str, product: str, direction: str, width: int, quantity: int, load_default: bool = False):
        if width < 1:
            raise ValueError('Invalid width')

        super().__init__(ticker, product, direction, width, quantity, load_default)

        self.name = s.STRATEGIES_BROAD[2]

        # Default expiry to tird Friday of next month
        expiry = m.third_friday()

        # Add legs. Long leg is always first!
        if product == 'call':
            if direction == 'long':
                self.add_leg(self.quantity, product, 'long', self.initial_spot, expiry)
                self.add_leg(self.quantity, product, 'short', self.initial_spot + DEFAULT_WIDTH, expiry)
            else:
                self.add_leg(self.quantity, product, 'long', self.initial_spot + DEFAULT_WIDTH, expiry)
                self.add_leg(self.quantity, product, 'short', self.initial_spot, expiry)
        else:
            if direction == 'long':
                self.add_leg(self.quantity, product, 'long', self.initial_spot + DEFAULT_WIDTH, expiry)
                self.add_leg(self.quantity, product, 'short', self.initial_spot, expiry)
            else:
                self.add_leg(self.quantity, product, 'long', self.initial_spot, expiry)
                self.add_leg(self.quantity, product, 'short', self.initial_spot + DEFAULT_WIDTH, expiry)

        if load_default:
            _, _, contracts = self.fetch_default_contracts()
            if len(contracts) == 2:
                self.legs[0].option.load_contract(contracts[0])
                self.legs[1].option.load_contract(contracts[1])
            else:
                _logger.error(f'{__name__}: Error fetching default contracts')

    def __str__(self):
        return f'{self.name} {self.product} {self.analysis.credit_debit} spread'

    def fetch_default_contracts(self, distance: int = 1, weeks: int = -1) -> tuple[str, int, list[str]]:
        # super() fetches the long option & itm index
        product, index, contracts = super().fetch_default_contracts(distance, weeks)

        if self.product == 'call':
            if self.direction == 'long':
                index += self.width
            else:
                index -= self.width
        elif self.direction == 'long':
            index -= self.width
        else:
            index += self.width

        options = self.chain.get_chain(product)

        # Add the short option
        contracts += [options.iloc[index]['contractSymbol']]

        return product, index, contracts

    @Threaded.threaded
    def analyze(self) -> None:
        ''' Analyze the strategy (Important: Assumes the long leg is the index-0 leg)'''

        if self._validate():
            self.task_error = 'None'

            self.task_message = self.legs[0].option.ticker

            self.legs[0].calculate(self.legs[0].option.strike)
            self.legs[1].calculate(self.legs[0].option.strike)

            price_long = self.legs[0].option.last_price if self.legs[0].option.last_price > 0.0 else self.legs[0].option.calc_price
            price_short = self.legs[1].option.last_price if self.legs[1].option.last_price > 0.0 else self.legs[1].option.calc_price

            dlong = (price_long > price_short)
            if dlong:
                self.analysis.credit_debit = 'debit'
            else:
                self.analysis.credit_debit = 'credit'

            # Calculate net debit or credit
            self.analysis.amount = abs(price_long - price_short) * self.quantity

            # Calculate min-max
            self.analysis.max_gain, self.analysis.max_loss, self.analysis.upside, self.analysis.sentiment = self.calculate_gain_loss()

            # Calculate breakeven
            self.analysis.breakeven = self.calculate_breakeven()

            # Generate profit table
            self.analysis.table = self.generate_profit_table()

        self.task_error = 'Done'

    def generate_profit_table(self) -> pd.DataFrame:
        if self.analysis.credit_debit == 'credit':
            profit = ((self.legs[0].value - self.legs[1].value) * self.quantity) + self.analysis.amount
        else:
            profit = ((self.legs[0].value - self.legs[1].value) * self.quantity) - self.analysis.amount

        return profit

    def calculate_gain_loss(self) -> tuple[float, float, float, str]:
        max_gain = max_loss = 0.0

        price_long = self.legs[0].option.last_price if self.legs[0].option.last_price > 0.0 else self.legs[0].option.calc_price
        price_short = self.legs[1].option.last_price if self.legs[1].option.last_price > 0.0 else self.legs[1].option.calc_price

        debit = (price_long > price_short)
        if self.product == 'call':
            if debit:
                max_loss = self.analysis.amount
                max_gain = (self.quantity * (self.legs[1].option.strike - self.legs[0].option.strike)) - max_loss
                upside = 0.0
                sentiment = 'bullish'
            else:
                max_gain = self.analysis.amount
                max_loss = (self.quantity * (self.legs[0].option.strike - self.legs[1].option.strike)) - max_gain
                upside = 0.0
                sentiment = 'bearish'
        else:
            if debit:
                max_loss = self.analysis.amount
                max_gain = (self.quantity * (self.legs[0].option.strike - self.legs[1].option.strike)) - max_loss
                upside = 0.0
                sentiment = 'bearish'
            else:
                max_gain = self.analysis.amount
                max_loss = (self.quantity * (self.legs[1].option.strike - self.legs[0].option.strike)) - max_gain
                upside = 0.0
                sentiment = 'bullish'

        return max_gain, max_loss, upside, sentiment

    def calculate_breakeven(self) -> float:
        if self.analysis.credit_debit == 'debit':
            breakeven = self.legs[1].option.strike + self.analysis.amount
        else:
            breakeven = self.legs[1].option.strike - self.analysis.amount

        return breakeven

    def get_errors(self) -> str:
        error = ''
        if self.analysis.credit_debit:
            if self.product == 'call':
                if self.analysis.credit_debit == 'debit':
                    if self.legs[0].option.strike >= self.legs[1].option.strike:
                        error = 'Bad option configuration'
                elif self.legs[1].option.strike >= self.legs[0].option.strike:
                    error = 'Bad option configuration'
            else:
                if self.analysis.credit_debit == 'debit':
                    if self.legs[1].option.strike >= self.legs[0].option.strike:
                        error = 'Bad option configuration'
                elif self.legs[0].option.strike >= self.legs[1].option.strike:
                    error = 'Bad option configuration'

        return error

    def _validate(self) -> bool:
        return len(self.legs) == 2


if __name__ == '__main__':
    import logging
    ui.get_logger(logging.INFO)

    call = Vertical('MSFT', 'call', 'long', 1)
    call.legs[0].calculate(call.legs[0].option.strike, value_table=False, greeks=False)
    output = f'${call.legs[0].option.calc_price:.2f}, ({call.legs[0].option.strike:.2f})'
    print(output)
    output = f'${call.legs[1].option.calc_price:.2f}, ({call.legs[1].option.strike:.2f})'
    print(output)
