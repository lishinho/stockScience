import pandas as pd
import akshare as ak
from datetime import datetime, timedelta

# ========== 数据获取模块 ==========
class DataFetcher:
    @staticmethod
    def fetch_stock_data(symbol, start_date, end_date):
        """通过AKShare获取股票历史数据"""
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date)
        df.rename(columns={
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume'
        }, inplace=True)
        df['date'] = pd.to_datetime(df['date'])
        return df.set_index('date')

    @staticmethod
    def get_hs300_symbols():
        """获取沪深300成分股代码"""
        try:
            hs300 = ak.index_stock_cons(symbol="000300")
            hs300 = hs300.drop_duplicates(subset=['品种代码'], keep='first')
            hs300['symbol'] = hs300['品种代码'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(6)
            hs300['symbol'] = hs300['symbol'].apply(lambda x: f"{x}.SZ" if x.startswith(('0','3')) else f"{x}.SH")
            return hs300['symbol'].drop_duplicates().tolist()
        except Exception as e:
            print(f"获取沪深300成分股失败: {str(e)}")
            return []