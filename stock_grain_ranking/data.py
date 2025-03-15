import pandas as pd
import akshare as ak

class DataFetcher:
    @staticmethod
    def get_stock_data(symbol, start_date):
        """获取股票数据"""
        try:
            df = ak.stock_zh_a_hist(symbol=symbol, start_date=start_date, adjust="hfq")
            df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '最高': 'high',
                '最低': 'low',
                '收盘': 'close',
                '成交量': 'volume'
            }, inplace=True)
            return df.set_index('date')
        except Exception as e:
            print(f"获取数据失败: {e}")
            return pd.DataFrame()

class DataCache:
    macro_data = {}
    stock_names = {}

    @classmethod
    def initialize(cls):
        cls.macro_data = {
            'cpi': cls._process_cpi_data(ak.macro_china_cpi()),
            'fx': ak.fx_spot_quote(),
            'pmi': ak.macro_china_pmi(),
            'gdp': ak.macro_china_gdp()
        }

    @staticmethod
    def _process_cpi_data(cpi_df):
        cpi_df['日期'] = pd.to_datetime(cpi_df.iloc[:,0].str.extract(r'(\d{4}年\d{1,2}月)')[0], format='%Y年%m月')
        return cpi_df.sort_values('日期')
