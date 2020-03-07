import datetime as dt

from red_rat import logger
from red_rat.app.mongo_connector import MongoConnector
from red_rat.app.market_data_provider import WorldTradingData
from red_rat.app.reuters_client import ReutersClient

mongo_connector = MongoConnector()
market_data_provider = WorldTradingData()

# TODO: update transcodification db
# TODO: gather fundamental data per stock into dataframe
# TODO: filter stocks from fundamental data
# TODO: TOR https://www.sylvaindurand.fr/use-tor-with-python/


@logger
def update_quotes():
    french_stocks = [stock for stock in market_data_provider.all_stocks if stock[3:] == ".PA"]
    for symbol in french_stocks:
        logger.log.info(f'updating {symbol}')
        quotes_to_insert = market_data_provider.get_historical_quotes(symbol)
        try:
            insert_quotes(quotes_to_insert)
        except KeyError:
            if quotes_to_insert['Message'].lower() == 'Error! The requested stock could not be found.'.lower():
                logger.log.warning(f"{symbol} not found")
        except Exception as e:
            raise e
    return


def insert_quotes(quotes):
    data_to_insert = []
    for close_date, daily_quote in quotes['history'].items():
        single_quote_to_insert = {
            'name': quotes['name'],
            'date': dt.datetime.fromisoformat(close_date),
            'open': float(daily_quote['open']) if daily_quote.get('open') is not None else None,
            'close': float(daily_quote['close']) if daily_quote.get('close') is not None else None,
            'high': float(daily_quote['high']) if daily_quote.get('high') is not None else None,
            'low': float(daily_quote['low']) if daily_quote.get('low') is not None else None,
            'volume': float(daily_quote['volume']) if daily_quote.get('volume') is not None else None,
            'source': market_data_provider.url
        }
        data_to_insert.append(single_quote_to_insert)
    mongo_connector.insert_documents(database_name='historical_quotes',
                                     collection_name='stocks',
                                     documents=data_to_insert)


@logger
def update_fundamentals():
    reuters = ReutersClient()
    data_to_insert = {'income': [], 'balance_sheet': [], 'cash_flow': []}
    stocks_from_mongo = mongo_connector.find_documents('static', 'stocks')

    for stock in stocks_from_mongo:
        if stock.get('ric') is not None:
            symbol = stock['ric']
        else:
            symbol = stock['symbol']

        fundamentals = reuters.get_financial_data(symbol)
        if fundamentals.get('status') and fundamentals['status']['code'] == 200:
            # if ric is not entered in DB, fill it
            if stock.get('ric') is None:
                mongo_connector.mongo_client.static.stocks.update({'_id': stock['_id']},
                                                                  {'$set': {'ric': stock['symbol']}})

            for statement, statement_data in fundamentals['market_data']['financial_statements'].items():
                for period, income_statements in statement_data.items():
                    for report_elem, reports in income_statements.items():
                        assert isinstance(reports, list)
                        for report in reports:
                            data = {'ric': fundamentals['ric'],
                                    'period': period,
                                    'report_elem': report_elem,
                                    'date': dt.datetime.fromisoformat(report['date']),
                                    'value': float(report['value'])}

                            data_to_insert[statement].append(data)
        else:
            logger.log.warning(f'{stock["symbol"]}: could not find fundamental data from reuters')
    for statement in data_to_insert:
        mongo_connector.insert_documents(database_name='fundamentals',
                                         collection_name=statement,
                                         documents=data_to_insert[statement])


def get_balance_sheet_elements(ric, period, date=None):
    query_filter = {'ric': ric, 'period': period}
    if date:
        query_filter.update({'date': date})
    balance_sheet_elems = mongo_connector.find_documents('fundamentals', 'balance_sheet', **query_filter)

    return balance_sheet_elems


def get_income_statement_elements(ric, period, date=None):
    query_filter = {'ric': ric, 'period': period}
    if date:
        query_filter.update({'date': date})
    income_statement_elems = mongo_connector.find_documents('fundamentals', 'income', **query_filter)

    return income_statement_elems


def get_cash_flow_statement_elements(ric, period, date=None):
    query_filter = {'ric': ric, 'period': period}
    if date:
        query_filter.update({'date': date})
    cash_flow_statement_elems = mongo_connector.find_documents('fundamentals', 'cash_flow', **query_filter)

    return cash_flow_statement_elems


if __name__ == '__main__':
    update_quotes()
    update_fundamentals()
    pass