from dataclasses import dataclass, field
import datetime as dt

import numpy as np
import pandas as pd

import strategies as s
from utils import ui


@dataclass()
class Analysis:
    ticker: str = ''
    credit_debit: s.OutlayType = s.OutlayType.Debit
    sentiment: s.SentimentType = s.SentimentType.Bullish
    total: float = 0.0
    max_gain: float = 0.0
    max_loss: float = 0.0
    upside: float = 0.0
    pop: float = 0.0
    score_options: float = -1.0
    score_screen: float = -1.0
    score_total: float = -1.0
    breakeven: list[float] = field(default_factory=list)
    profit_table: pd.DataFrame = pd.DataFrame()
    analysis: pd.DataFrame = pd.DataFrame()
    strategy: pd.DataFrame = pd.DataFrame()

    def __post_init__(self):
        self.sort_index = self.score_total

    def __str__(self):
        if not self.profit_table.empty:
            gain = 'Unlimited' if self.max_gain < 0.0 else f'${self.max_gain*100:.2f}'
            loss = 'Unlimited' if self.max_loss < 0.0 else f'${self.max_loss*100:.2f}'
            return_text = f'{self.upside * 100.0:.2f}%' if self.upside >= 0.0 else 'Unlimited'
            output = \
                f'Type:             {self.credit_debit.name.title()}\n'\
                f'Sentiment:        {self.sentiment.value.title()}\n'\
                f'Total:            {abs(self.total*100.0):.2f} {self.credit_debit.name}\n'\
                f'Max Gain:         {gain}\n'\
                f'Max Loss:         {loss}\n'\
                f'Return:           {return_text}\n'\
                f'POP:              {self.pop*100.0:.2f}%\n'\
                f'Score Options:    {self.score_options:.2f}\n'\
                f'Score Screen:     {self.score_screen:.2f}\n'\
                f'Score:            {self.score_total:.2f}\n'

            if len(self.breakeven) > 1:
                output += f'Breakeven1:       {self.breakeven[0]:.2f}\n'
                output += f'Breakeven2:       {self.breakeven[1]:.2f}\n'
            else:
                output += f'Breakeven:        {self.breakeven[0]:.2f}\n'
        else:
            output = 'Not yet analyzed\n'

        return output

    def summarize(self) -> None:
        if not self.profit_table.empty:
            self.score_total = self.score_options
            if self.score_screen > 0.0:
                self.score_total += self.score_screen

            data = {
                'credit_debit': self.credit_debit.name,
                'sentiment': self.sentiment.value.title(),
                'total': self.total * 100.0 if self.credit_debit == s.OutlayType.Credit else self.total * -100.0,
                'max_gain': self.max_gain * 100.0 if self.max_gain >= 0.0 else 'unlimited',
                'max_loss': self.max_loss * 100.0 if self.max_loss >= 0.0 else 'unlimited',
                'return': self.upside if self.upside >= 0.0 else 'unlimited',
                'pop': self.pop,
                'score_option': self.score_options,
                'score_screen': self.score_screen,
                'score_total': self.score_total
            }

            if len(self.breakeven) > 1:
                data['breakeven1'] = self.breakeven[0]
                data['breakeven2'] = self.breakeven[1]
            else:
                data['breakeven'] = self.breakeven[0]

            self.analysis = pd.DataFrame(data, index=[self.ticker])

    def set_strategy(self, name: str, strikes: list[float], expiry: dt.datetime, spot: float) -> None:
        data = {
            'strategy': name,
            'spot': f'{spot:.02f}',
            'strikes': np.array2string(np.array(strikes), precision=2, floatmode='fixed'),
            'expiry': expiry.strftime(ui.DATE_FORMAT_YMD),
        }

        self.strategy = pd.DataFrame(data, index=[self.ticker])

def calculate_sentiment(strategy: s.StrategyType, product: s.ProductType, direction: s.DirectionType) -> s.SentimentType:
    sentiment = s.SentimentType.Bullish
    if strategy == s.StrategyType.Call:
        if direction == s.DirectionType.Short:
            sentiment = s.SentimentType.Bearish
    elif strategy == s.StrategyType.Put:
        if direction == s.DirectionType.Long:
            sentiment = s.SentimentType.Bearish
    elif strategy == s.StrategyType.Vertical:
        if product == s.ProductType.Put and direction == s.DirectionType.Long:
            sentiment = s.SentimentType.Bearish
        if product == s.ProductType.Call and direction == s.DirectionType.Short:
            sentiment = s.SentimentType.Bearish
    elif strategy == s.StrategyType.IronCondor:
        if direction == s.DirectionType.Long:
            sentiment = s.SentimentType.HighVolatility
        else:
            sentiment = s.SentimentType.LowVolatility
    elif strategy == s.StrategyType.IronButterfly:
        if direction == s.DirectionType.Long:
            sentiment = s.SentimentType.HighVolatility
        else:
            sentiment = s.SentimentType.LowVolatility

    return sentiment
