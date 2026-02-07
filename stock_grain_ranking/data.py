import pandas as pd
import sys
import os
import akshare as ak
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_resilient import DataResilient
from cache_manager import CacheManager
from datetime import datetime, timedelta

class DataFetcher:
    @staticmethod
    def get_hs300_symbols():
        """获取沪深300成分股代码（与stockRanking.py保持完全一致）"""
        return DataResilient.get_hs300_symbols(use_cache=True)
            
    @staticmethod
    def fetch_stock_data(symbol, start_date, end_date):
        """通过AKShare获取股票历史数据（日线）- 带缓存和重试"""
        start_date_str = start_date.strftime("%Y%m%d") if hasattr(start_date, 'strftime') else start_date
        end_date_str = end_date.strftime("%Y%m%d") if hasattr(end_date, 'strftime') else end_date
        return DataResilient.fetch_stock_data(symbol, start_date_str, end_date_str, use_cache=True)

class DataCache:
    macro_data = {}
    stock_names = {}

    @classmethod
    def initialize(cls):
        CacheManager.initialize()
        
        try:
            DataCache.macro_data = {
                'cpi': DataResilient.fetch_macro_data('cpi', use_cache=True),
                'fx': DataResilient.fetch_macro_data('fx', use_cache=True),
                'pmi': DataResilient.fetch_macro_data('pmi', use_cache=True),
                'gdp': DataResilient.fetch_macro_data('gdp', use_cache=True)
            }
            
            if DataCache.macro_data['cpi'].empty:
                print("警告：CPI数据获取失败，使用默认值")
                DataCache.macro_data['cpi'] = pd.DataFrame({
                    '统计时间': [datetime.now().strftime("%Y年%m月")],
                    '全国-当月': [2.5]
                })
            
            cpi_df = DataCache.macro_data['cpi']
            if '日期' in cpi_df.columns:
                cpi_df['日期'] = pd.to_datetime(cpi_df['日期'], errors='coerce')
            elif '统计时间' in cpi_df.columns:
                cpi_df['日期'] = pd.to_datetime(cpi_df['统计时间'], format='%Y年%m月', errors='coerce')
            else:
                cpi_df['日期'] = pd.to_datetime(cpi_df.iloc[:,0].str.extract(r'(\d{4}年\d{1,2}月)')[0], format='%Y年%m月', errors='coerce')
            
            gdp_df = DataCache.macro_data['gdp']
            if not gdp_df.empty and '季度' in gdp_df.columns:
                gdp_df['季度日期'] = gdp_df['季度'].apply(lambda x: pd.Timestamp(year=int(x.split('年')[0]), 
                    month=(int(x.split('第')[1][0])*3-2), day=1))
            else:
                print("警告：GDP数据缺少季度字段，使用默认日期")
                if not gdp_df.empty:
                    gdp_df['季度日期'] = pd.Timestamp.now()
                else:
                    gdp_df = pd.DataFrame({'季度日期': [pd.Timestamp.now()]})
            
            stock_info = DataResilient.get_stock_info(use_cache=True)
            if not stock_info.empty:
                cls.stock_names = dict(zip(stock_info['code'], stock_info['name']))
        except Exception as e:
            print(f"数据初始化失败: {e}")
            cls.stock_names = {}
