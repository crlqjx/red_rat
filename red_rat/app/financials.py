import datetime as dt
from red_rat.app import euronext, reuters, mongo
from red_rat.app.helpers import Helpers


class Financials:
    def __init__(self, **kwargs):
        self._mongo = mongo
        self._euronext = euronext
        self._reuters = reuters
        self._helpers = Helpers()

        self.isin, self.ric = Helpers().transco_isin_ric(**kwargs)
        self.mic = kwargs.get('mic')

        self._instrument_details = self._euronext.get_instrument_details(self.isin, self.mic)

    def eps(self, annual_period: bool = False, eps_date: dt.datetime = None):
        period = 'annual' if annual_period else 'interim'
        if eps_date:
            query = {'ric': self.ric, 'report_elem': 'Net Income', 'period': period, 'date': eps_date}
        else:
            query = {'ric': self.ric, 'report_elem': 'Net Income', 'period': period}
        net_income = self._mongo.find_documents(database_name='financials',
                                                collection_name='income',
                                                sort=[('date', -1)],
                                                **query)
        net_income = net_income.__next__()['value'] * 1e6

        outs_shares = int(self._instrument_details['instr']['nbShare'])

        eps = net_income / outs_shares

        return eps

    def per(self, price_date: dt.date = None):
        # Get last price
        if price_date is None:
            # from euronext
            price = float(self._instrument_details['instr']['currInstrSess']['lastPx'])

        else:
            # from mongo
            price = float(self._helpers.get_price_from_mongo(self.isin, price_date))

        eps = self.eps()
        per = price / eps
        return per
