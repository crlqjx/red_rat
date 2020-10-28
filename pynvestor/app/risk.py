import pandas as pd
import numpy as np

from pynvestor.app.portfolio import Portfolio
from pynvestor.app.helpers import Helpers


class PortfolioRiskManager(Portfolio):
    """
    class to manage portfolio risks
    """

    def __init__(self, risk_free_rate: float, portfolio_path: str = None, lookback_days: int = 500):
        super().__init__(portfolio_path)

        self._lookback_days = lookback_days

        self._compute_nav_volatility()
        self._compute_assets_returns()
        self._compute_portfolio_volatility()
        self._compute_portfolio_sharpe_ratio(risk_free_rate)
        self._compute_portfolio_value_at_risk()

    def _compute_assets_returns(self):
        """
        Compute assets daily returns
        :return:
        """
        returns = []
        for isin, _ in self.stocks_weights.items():
            returns.append(self._helpers.get_returns(isin=isin,
                                                     sort=[("time", -1)],
                                                     window=self._lookback_days).values)

        returns = np.stack(returns)
        self._histo_returns = returns
        return True

    def _compute_portfolio_volatility(self):
        """
        compute portfolio volatility from the assets covariance matrix
        :return:
        """
        weights = np.array(list(self.stocks_weights.values()))

        portfolio_variance, cov_matrix = Helpers.compute_portfolio_variance(weights, self._histo_returns)
        self._covariance_matrix = cov_matrix
        self._assets_std = {list(self.stocks_weights.keys())[i]: cov_matrix[i][i] for i in range(len(weights))}
        self._annualized_portfolio_volatility = np.sqrt(portfolio_variance)
        return True

    def _compute_nav_volatility(self):
        """
        Compute portfolio volatility of NAV since inception
        :return: float value
        """
        self._nav_volatility = self.nav_weekly_returns.std()
        return True

    def _compute_portfolio_sharpe_ratio(self, risk_free_rate: float):
        """
        compute portfolio sharpe ratios compared to a fixed risk-free rate
        :param risk_free_rate: float
        :return: series
        """

        weights = np.array(list(self.stocks_weights.values()))
        mean_returns = np.array([self._histo_returns[i].mean() for i in range(len(self._histo_returns))])
        self._mean_returns = mean_returns
        annualized_mean_returns = (1 + mean_returns) ** 252 - 1
        annualized_portfolio_return = np.sum(weights * annualized_mean_returns)

        sharpe_ratio = Helpers.compute_sharpe_ratio(annualized_portfolio_return,
                                                    self._annualized_portfolio_volatility,
                                                    risk_free_rate)
        self._portfolio_sharpe_ratio = sharpe_ratio

        return True

    def _compute_portfolio_value_at_risk(self,
                                         method: str = "historical",
                                         percentile: int = 5):
        """
        compute portfolio Value At Risk
        :param method: method of computation for the value at risk
        :param percentile: confidence interval
        :return:
        """

        if method == "historical":

            # Get simulated historical portfolio value
            df_assets_market_values = pd.DataFrame()
            for isin, quantity in self.stocks_quantities.items():
                prices_series = self._helpers.get_prices_from_mongo(isin=isin,
                                                                    sort=[("time", -1)],
                                                                    window=self._lookback_days)
                total_market_value = prices_series * quantity
                df_assets_market_values[isin] = total_market_value

            portfolio_market_values_series = df_assets_market_values.sum(axis=1)
            portfolio_market_values_series.sort_index(inplace=True)
            portfolio_changes_series = portfolio_market_values_series * portfolio_market_values_series.pct_change()
            portfolio_changes_series.dropna(inplace=True)

            sorted_results = portfolio_changes_series.values
            percentile_loc = int(round(percentile / 100 * len(sorted_results), 0))
            value_at_risk = sorted_results[percentile_loc]

        elif method == "normal":
            raise NotImplementedError

        else:
            raise NotImplementedError

        self._portfolio_value_at_risk = value_at_risk
        return True

    @property
    def lookback_days(self):
        return self._lookback_days

    @property
    def assets_std(self):
        return self._assets_std

    @property
    def nav_volatility(self):
        return self._nav_volatility

    @property
    def annualized_portfolio_volatility(self):
        return self._annualized_portfolio_volatility

    @property
    def portfolio_sharpe_ratio(self):
        return self._portfolio_sharpe_ratio

    @property
    def portfolio_value_at_risk(self):
        return self._portfolio_value_at_risk