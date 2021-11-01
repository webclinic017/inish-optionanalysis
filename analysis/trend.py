'''
trendln: https://github.com/GregoryMorse/trendln
         https://towardsdatascience.com/programmatic-identification-of-support-resistance-trend-lines-with-python-d797a4a90530,
'''

import math

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import trendln

from base import Threaded
from data import store as store
from utils import utils

_logger = utils.get_logger()
_rounding = 0.075

METHOD = {
    'NCUBED': trendln.METHOD_NCUBED,
    'NSQUREDLOGN': trendln.METHOD_NSQUREDLOGN,
    # 'HOUGHPOINTS': trendln.METHOD_HOUGHPOINTS, # Bug in trendln
    'HOUGHLINES': trendln.METHOD_HOUGHLINES,
    'PROBHOUGH': trendln.METHOD_PROBHOUGH
}

EXTMETHOD = {
    'NAIVE': trendln.METHOD_NAIVE,
    'NAIVECONSEC': trendln.METHOD_NAIVECONSEC,
    'NUMDIFF': trendln.METHOD_NUMDIFF
}

MAX_SCALE = 10.0
ACCURACY = 4

class _Score:
    def __init__(self):
        self.fit = 0.0
        self.width = 0.0
        self.proximity = 0.0
        self.points = 0.0
        self.age = 0.0
        self.slope = 0.0
        self.basis = True

    def calculate(self) -> float:
        score = (
            (self.fit       * 0.05) +
            (self.width     * 0.15) +
            (self.proximity * 0.05) +
            (self.points    * 0.20) +
            (self.age       * 0.20) +
            (self.slope     * 0.30))

        if self.basis: score += 0.05

        return score

class _Line:
    def __init__(self):
        self.support = False
        self.points = []
        self.end_point = 0.0
        self.slope = 0.0
        self.intercept = 0.0
        self.fit = 0
        self.ssr = 0.0
        self.slope_err = 0.0
        self.intercept_err = 0.0
        self.area_avg = 0.0
        self.width = 0.0
        self.age = 0.0
        self.proximity = 0.0
        self.score = 0.0
        self._score = _Score()

    def __str__(self):
        dates = [point['date'] for point in self.points]
        output = f'score={self.score:.2f}, '\
                 f'fit={self.fit:4n} '\
                 f'wid={self.width:4n} '\
                 f'prox={self.proximity:5.1f} '\
                 f'pnts={len(dates)} '\
                 f'age={self.age:4n} '\
                 f'slope={self.slope:4n} '\
                 f'*fit={self.score.fit:5.2f} '\
                 f'*wid={self.score.width:5.2f} '\
                 f'*prox={self.score.proximity:5.2f} '\
                 f'*pnts={self.score.points:5.2f} '\
                 f'*age={self.score.age:5.2f}'\
                 f'*slope={self.score.slope:5.2f}'

        return output

class _Stats:
    def __init__(self):
        self.res_slope = 0.0
        self.res_intercept = 0.0
        self.res_weighted_mean = 0.0
        self.res_weighted_std = 0.0
        self.res_level = 0.0
        self.sup_slope = 0.0
        self.sup_intercept = 0.0
        self.sup_weighted_mean = 0.0
        self.sup_weighted_std = 0.0
        self.sup_level = 0.0

class SupportResistance(Threaded):
    def __init__(self, ticker:str, methods:list[str]=['NSQUREDLOGN'], extmethods:list[str]=['NUMDIFF'], best:int=8, days:int=1000):
        if best < 1:
            raise ValueError("'best' value must be > 0")

        if days <= 30:
            raise ValueError('Days must be greater than 30')

        if (store.is_ticker(ticker)):
            self.ticker = ticker.upper()
            self.methods = methods
            self.extmethods = extmethods
            self.best = best
            self.days = days
            self.history = pd.DataFrame()
            self.price = 0.0
            self.company = {}
            self.lines = pd.DataFrame()
            self.stats = _Stats()
        else:
            raise ValueError('{__name__}: Error initializing {__class__} with ticker {ticker}')

    def __str__(self):
        return f'Support and resistance analysis for {self.ticker} (${self.price:.2f})'

    @Threaded.threaded
    def calculate(self) -> None:
        self.history = store.get_history(self.ticker, self.days)
        if self.history is None:
            raise ValueError('Unable to get history')

        self.task_message = self.ticker

        self.price = self.history.iloc[-1]['close']
        self.company = store.get_company(self.ticker)
        if not self.company:
            self.company['name'] = 'Error'
            _logger.warning(f'Unable to get company information ({self.ticker})')

        self.points = len(self.history)
        self.task_error = 'None'

        # Extract lines across methods, extmethods, and then flatten the results
        lines = [self._extract_lines(method, extmethod) for method in self.methods for extmethod in self.extmethods]
        lines = [item for sublist in lines for item in sublist]

        self.task_total = len(lines)
        _logger.info(f'{__name__}: {self.task_total} total lines extracted')

        # Create dataframe of lines then sort, round, and drop duplicates
        df = pd.DataFrame.from_records([vars(l) for l in lines])
        df.dropna(inplace=True)
        df.drop('_score', 1, inplace=True)
        df.sort_values(by=['score'], ascending=False, inplace=True)
        df = df.round(6)
        df.drop_duplicates(subset=['slope', 'intercept'], inplace=True)
        self.lines = df.reset_index(drop=True)
        _logger.info(f'{__name__}: {len(self.lines)} rows created ({len(lines)-len(self.lines)} duplicates deleted)')

        self._calculate_stats()

        self.task_error = 'Hold'

    def _extract_lines(self, method:str, extmethod:str) -> list[_Line]:
        if not method in METHOD:
            assert ValueError(f'Invalid method {method}')

        result = trendln.calc_support_resistance((None, self.history['high']), method=METHOD[method], extmethod=EXTMETHOD[extmethod], accuracy=ACCURACY)
        maximaIdxs, pmax, maxtrend, maxwindows = result

        result = trendln.calc_support_resistance((self.history['low'], None), method=METHOD[method], extmethod=EXTMETHOD[extmethod], accuracy=ACCURACY)
        minimaIdxs, pmin, mintrend, minwindows = result

        self.stats.res_slope = pmax[0]
        self.stats.res_intercept = pmax[1]

        lines:list[_Line] = []
        for line in maxtrend:
            newline = _Line()
            newline.support = False
            newline.end_point = 0.0
            newline.points = [{'index':point, 'date':''} for point in line[0]]
            newline.slope = line[1][0]
            newline.intercept = line[1][1]
            newline.ssr = line[1][2]
            newline.slope_err = line[1][3]
            newline.intercept_err = line[1][4]
            newline.area_avg = line[1][5]

            newline.width = newline.points[-1]['index'] - newline.points[0]['index']
            newline.age = self.points - newline.points[-1]['index']

            lines += [newline]

        self.stats.sup_slope = pmin[0]
        self.stats.sup_intercept = pmin[1]

        for line in mintrend:
            newline = _Line()
            newline.support = True
            newline.end_point = 0.0
            newline.points = [{'index':point, 'date':''} for point in line[0]]
            newline.slope = line[1][0]
            newline.intercept = line[1][1]
            newline.ssr = line[1][2]
            newline.slope_err = line[1][3]
            newline.intercept_err = line[1][4]
            newline.area_avg = line[1][5]

            newline.width = newline.points[-1]['index'] - newline.points[0]['index']
            newline.age = self.points - newline.points[-1]['index']

            lines += [newline]

        # Calculate dates of pivot points
        for line in lines:
            for point in line.points:
                date = self.history['date'].iloc[point['index']]
                point['date'] = [date.strftime('%Y-%m-%d')]

        # Calculate end point extension (y = mx + b)
        for line in lines:
            line.end_point = (line.slope * self.points) + line.intercept
            if line.end_point < 0.0: line.end_point = 0.0

        # Sort lines based on mathematical fit (ssr) and set the line ranking
        lines = sorted(lines, key=lambda l: l.ssr)
        for index, line in enumerate(lines):
            line.fit = index + 1

        ##   Normalize scoring criteria to MAX_SCALE scale ##

        #    Rank
        max_ = 0.0
        for line in lines:
            if line.fit > max_: max_ = line.fit
        for line in lines:
            line._score.fit = line.fit / max_
            line._score.fit *= MAX_SCALE
            line._score.fit = MAX_SCALE - line._score.fit # Lower is better

        #    Width
        max_ = 0.0
        for line in lines:
            if line.width > max_: max_ = line.width
        for line in lines:
            line._score.width = line.width / max_
            line._score.width *= MAX_SCALE

        #    Proximity
        max_ = 0.0
        for line in lines:
            line.proximity = abs(line.end_point - self.price)
            if line.proximity > max_: max_ = line.proximity
        for line in lines:
            line._score.proximity = line.proximity / max_
            line._score.proximity *= MAX_SCALE
            line._score.proximity = MAX_SCALE - line._score.proximity # Lower is better

        #    Points
        max_ = 0.0
        for line in lines:
            if len(line.points) > max_: max_ = len(line.points)
        for line in lines:
            line._score.points = len(line.points) / max_
            line._score.points *= MAX_SCALE

        #    Age
        max_ = 0.0
        for line in lines:
            if line.age > max_: max_ = line.age
        for line in lines:
            line._score.age = line.age / max_
            line._score.age *= MAX_SCALE
            line._score.age = MAX_SCALE - line._score.age # Lower is better

        #    Slope
        max_ = 0.0
        for line in lines:
            if line.slope > max_: max_ = abs(line.slope)
        for line in lines:
            line._score.slope = abs(line.slope) / max_
            line._score.slope *= MAX_SCALE
            line._score.slope = MAX_SCALE - line._score.slope # Lower is better

        #   Basis (line type matches position. Ex: end point of support line is below current price, resistence end point above)
        for line in lines:
            if line.support:
                line._score.basis = True if line.end_point < self.price else False
            else:
                line._score.basis = True if line.end_point >= self.price else False

        for line in lines:
            line.score = line._score.calculate()

        _logger.info(f'{__name__}: {len(lines)} lines extracted using {method} and {extmethod}')

        return lines

    def _get_resistance(self, method_price:bool=True, best:int=0) -> pd.DataFrame:
        if best <= 0: best = self.best

        df = self.lines[self.lines['support'] == False].copy()
        df = df.sort_values(by=['score'], ascending=False)[:best]

        if method_price:
            dfs = self._get_support(method_price=False)
            df = pd.concat([df, dfs])
            df = df[df['end_point'] >= self.price]
            df = df.sort_values(by=['end_point'], ascending=True)

        df.reset_index(drop=True, inplace=True)

        return df

    def _get_support(self, method_price:bool=True, best:int=0) -> pd.DataFrame:
        if best <= 0: best = self.best

        df = self.lines[self.lines['support'] == True].copy()
        df = df.sort_values(by=['score'], ascending=False)[:best]

        if method_price:
            dfr = self._get_resistance(method_price=False)
            df = pd.concat([df, dfr])
            df = df[df['end_point'] < self.price]
            df = df.sort_values(by=['end_point'], ascending=False)

        df.reset_index(drop=True, inplace=True)

        return df

    def _calculate_stats(self, best:int=0) -> None:
        if best <= 0: best = self.best

        def calculate(support:bool) -> tuple[float, float, float]:
            weighted_mean = 0.0
            weighted_std = 0.0
            level = 0.0

            if support:
                df = self._get_support(best=best)
            else:
                df = self._get_resistance(best=best)

            if not df.empty:
                norm = max(df['score'].to_list())
                values = df['end_point'].to_list()
                weights = [df.iloc[n]['score'] / norm for n in range(len(df))]

                # Closest end point to price
                level = values[0]

                # Weighted average according to scores
                weighted_mean = np.average(values, weights=weights)

                # Std Dev
                variance = np.average((values-weighted_mean)**2, weights=weights)
                weighted_std = math.sqrt(variance)
            else:
                _logger.info(f'{__name__}: Empty dataframe calculating stats')

            return weighted_mean, weighted_std, level

        # Resistance
        self.stats.res_weighted_mean, self.stats.res_weighted_std, self.stats.res_level = calculate(False)
        _logger.info(f'{__name__}: Res: wmean={self.stats.res_weighted_mean:.2f}, wstd={self.stats.res_weighted_std:.2f}, level={self.stats.res_level}')

        # Support
        self.stats.sup_weighted_mean, self.stats.sup_weighted_std, self.stats.sup_level = calculate(True)
        _logger.info(f'{__name__}: Sup: wmean={self.stats.sup_weighted_mean:.2f}, wstd={self.stats.sup_weighted_std:.2f}, level={self.stats.sup_level}')

    def plot(self, show:bool=False, legend:bool=True, trendlines:bool=False, filename:str='') -> plt.Figure:
        resistance = self._get_resistance(method_price=False)
        support = self._get_support(method_price=False)

        plt.style.use('seaborn-bright')
        figure, ax1 = plt.subplots(figsize=(17,10))
        plt.grid()
        plt.margins(x=0.1)
        plt.title(f'{self.company["name"]}')
        figure.canvas.manager.set_window_title(f'{self.ticker} Support & Resistance')
        line_width = 1.0

        if self.price < 30.0:
            ax1.yaxis.set_major_formatter('{x:.2f}')
        else:
            ax1.yaxis.set_major_formatter('{x:.0f}')

        ax1.secondary_yaxis('right')

        # Highs & Lows
        length = len(self.history)
        dates = [self.history.iloc[index]['date'].strftime('%Y-%m-%d') for index in range(length)]

        plt.xticks(range(0, length+1, int(length/12)))
        plt.xticks(rotation=45)
        plt.subplots_adjust(bottom=0.15)

        ax1.plot(dates, self.history['high'], '-g', linewidth=0.5)
        ax1.plot(dates, self.history['low'], '-r', linewidth=0.5)
        ax1.fill_between(dates, self.history['high'], self.history['low'], facecolor='gray', alpha=0.4)

        # Pivot points
        dates = []
        values = []
        for line in resistance.itertuples():
            for point in line.points:
                index = point['index']
                date = self.history.iloc[index]['date']
                dates += [date.strftime('%Y-%m-%d')]
                values += [self.history.iloc[index]['high']]
        ax1.plot(dates, values, '.r')

        dates = []
        values = []
        for line in support.itertuples():
            for point in line.points:
                index = point['index']
                date = self.history.iloc[index]['date']
                dates += [date.strftime('%Y-%m-%d')]
                values += [self.history.iloc[index]['low']]
        ax1.plot(dates, values, '.g')

        # Trend lines
        dates = []
        values = []
        for line in resistance.itertuples():
            index = line.points[0]['index']
            date = self.history.iloc[index]['date']
            dates = [date.strftime('%Y-%m-%d')]
            values = [self.history.iloc[index]['high']]
            index = line.points[-1]['index']
            date = self.history.iloc[index]['date']
            dates += [date.strftime('%Y-%m-%d')]
            values += [self.history.iloc[index]['high']]

            ax1.plot(dates, values, '-r', linewidth=line_width)

        dates = []
        values = []
        for line in support.itertuples():
            index = line.points[0]['index']
            date = self.history.iloc[index]['date']
            dates = [date.strftime('%Y-%m-%d')]
            values = [self.history.iloc[index]['low']]
            index = line.points[-1]['index']
            date = self.history.iloc[index]['date']
            dates += [date.strftime('%Y-%m-%d')]
            values += [self.history.iloc[index]['low']]

            ax1.plot(dates, values, '-g', linewidth=line_width)

        # Trend line extensions
        dates = []
        values = []
        for line in resistance.itertuples():
            index = line.points[-1]['index']
            date = self.history.iloc[index]['date']
            dates = [date.strftime('%Y-%m-%d')]
            values = [self.history.iloc[index]['high']]
            index = self.points-1
            date = self.history.iloc[index]['date']
            dates += [date.strftime('%Y-%m-%d')]
            values += [line.end_point]

            ax1.plot(dates, values, ':r', linewidth=line_width)

        dates = []
        values = []
        for line in support.itertuples():
            index = line.points[-1]['index']
            date = self.history.iloc[index]['date']
            dates = [date.strftime('%Y-%m-%d')]
            values = [self.history.iloc[index]['low']]
            index = self.points-1
            date = self.history.iloc[index]['date']
            dates += [date.strftime('%Y-%m-%d')]
            values += [line.end_point]

            ax1.plot(dates, values, ':g', linewidth=line_width)

        # End points
        dates = []
        values = []
        text = []
        for index, line in enumerate(resistance.itertuples()):
            ep = utils.mround(line.end_point, _rounding)
            if ep not in values:
                date = self.history['date'].iloc[-1]
                dates += [date.strftime('%Y-%m-%d')]
                values += [ep]
                text += [{'text':f'{line.end_point:.2f}:{index+1}', 'value':line.end_point, 'color':'red'}]
        ax1.plot(dates, values, '.r')

        dates = []
        values = []
        for index, line in enumerate(support.itertuples()):
            ep = utils.mround(line.end_point, _rounding)
            if ep not in values:
                date = self.history['date'].iloc[-1]
                dates += [date.strftime('%Y-%m-%d')]
                values += [ep]
                text += [{'text':f'{line.end_point:.2f}:{index+1}', 'value':line.end_point, 'color':'green'}]
        ax1.plot(dates, values, '.g')

        # End points text
        ylimits = ax1.get_ylim()
        inc = (ylimits[1] - ylimits[0]) / 33.0
        text = sorted(text, key=lambda t: t['value'])
        index = 1
        for txt in text:
            if txt['value'] > self.price:
                ax1.text(self.points+5, self.price+(index*inc), txt['text'], color=txt['color'], va='center', size='small')
                index += 1

        text = sorted(text, reverse=True, key=lambda t: t['value'])
        index = 1
        for txt in text:
            if txt['value'] < self.price:
                ax1.text(self.points+5, self.price-(index*inc), txt['text'], color=txt['color'], va='center', size='small')
                index += 1

        # Price line
        ax1.hlines(self.price, -20, self.points, color='black', linestyle='--', label='Current Price', linewidth=1.0)
        ax1.text(self.points+5, self.price, f'{self.price:.2f}', color='black', va='center', size='small')

        # Aggregate resistance & support lines
        if self.stats.res_level > 0.0:
            ax1.hlines(self.stats.res_level, -20, self.points, color='red', linestyle='-.', label='Aggregate Resistance', linewidth=1.0)

        if self.stats.sup_level > 0.0:
            ax1.hlines(self.stats.sup_level, -20, self.points, color='green', linestyle='-.', label='Aggregate Support', linewidth=1.0)

        # Trendlines
        if trendlines:
            index = 0
            date = self.history.iloc[index]['date']
            dates = [date.strftime('%Y-%m-%d')]
            values = [self.stats.res_intercept]
            index = self.points-1
            date = self.history.iloc[index]['date']
            dates += [date.strftime('%Y-%m-%d')]
            values += [self.stats.res_slope * self.points + self.stats.res_intercept]

            ax1.plot(dates, values, '--', color='darkgreen', label='Avg Resistance', linewidth=1.7)

            index = 0
            date = self.history.iloc[index]['date']
            dates = [date.strftime('%Y-%m-%d')]
            values = [self.stats.sup_intercept]
            index = self.points-1
            date = self.history.iloc[index]['date']
            dates += [date.strftime('%Y-%m-%d')]
            values += [self.stats.sup_slope * self.points + self.stats.sup_intercept]

            ax1.plot(dates, values, '--', color='darkred', label='Avg Support', linewidth=1.7)

        if legend:
            plt.legend(loc='upper left')

        if filename:
            figure.savefig(filename, dpi=150)
            _logger.info(f'{__name__}: Saved plot as {filename}')

        if show:
            plt.show()

        return figure


if __name__ == '__main__':
    import sys
    import logging

    utils.get_logger(logging.DEBUG)

    if len(sys.argv) > 1:
        methods = ['NSQUREDLOGN', 'NCUBED', 'HOUGHLINES', 'PROBHOUGH']
        extmethods = ['NAIVE', 'NAIVECONSEC', 'NUMDIFF']
        sr = SupportResistance(sys.argv[1])
        # sr = SupportResistance(sys.argv[1], methods=methods, extmethods=extmethods)
    else:
        sr = SupportResistance('AAPL')

    sr.calculate()
    sr.plot(show=True)