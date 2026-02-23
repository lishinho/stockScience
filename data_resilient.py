import pandas as pd
import akshare as ak
import time
import random
import threading
from datetime import datetime
from cache_manager import CacheManager

class RequestLimiter:
    _instance = None
    _lock = threading.Lock()
    _last_request_time = 0
    _min_interval = 0.5
    
    @classmethod
    def acquire(cls):
        with cls._lock:
            current_time = time.time()
            elapsed = current_time - cls._last_request_time
            if elapsed < cls._min_interval:
                wait_time = cls._min_interval - elapsed + random.uniform(0.1, 0.3)
                time.sleep(wait_time)
            cls._last_request_time = time.time()

class DataResilient:
    MAX_RETRIES = 5
    BASE_DELAY = 1.0
    MAX_DELAY = 10.0
    
    @staticmethod
    def fetch_stock_data(symbol: str, start_date: str, end_date: str, use_cache: bool = True) -> pd.DataFrame:
        if use_cache:
            cached_data = CacheManager.load_stock_cache(symbol, start_date, end_date)
            if cached_data is not None:
                return cached_data
        
        df = DataResilient._fetch_with_retry(symbol, start_date, end_date)
        
        if use_cache and df is not None and not df.empty:
            CacheManager.save_stock_cache(symbol, start_date, end_date, df)
        
        return df
    
    @staticmethod
    def _fetch_with_retry(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        last_exception = None
        
        for attempt in range(DataResilient.MAX_RETRIES):
            try:
                RequestLimiter.acquire()
                
                df = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date
                )
                
                if df is None or df.empty:
                    raise ValueError(f"获取数据为空: {symbol}")
                
                df.rename(columns={
                    '日期': 'date',
                    '开盘': 'open',
                    '收盘': 'close',
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'volume'
                }, inplace=True)
                
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                
                return df
                
            except Exception as e:
                last_exception = e
                if attempt < DataResilient.MAX_RETRIES - 1:
                    delay = min(DataResilient.BASE_DELAY * (2 ** attempt) + random.uniform(0, 1), DataResilient.MAX_DELAY)
                    print(f"重试获取 {symbol} (第{attempt + 1}次) - 延迟 {delay:.1f}秒... 错误: {str(e)[:50]}")
                    time.sleep(delay)
                else:
                    print(f"获取 {symbol} 失败: {str(e)}")
                    raise
    
    @staticmethod
    def fetch_macro_data(data_type: str, use_cache: bool = True) -> pd.DataFrame:
        if use_cache:
            cached_data = CacheManager.load_macro_cache(data_type)
            if cached_data is not None:
                return cached_data
        
        df = DataResilient._fetch_macro_with_retry(data_type)
        
        if use_cache and df is not None and not df.empty:
            CacheManager.save_macro_cache(data_type, df)
        
        return df
    
    @staticmethod
    def _fetch_macro_with_retry(data_type: str) -> pd.DataFrame:
        fetch_functions = {
            'cpi': lambda: ak.macro_china_cpi(),
            'gdp': lambda: ak.macro_china_gdp(),
            'pmi': lambda: ak.macro_china_pmi(),
            'fx': lambda: ak.fx_spot_quote()
        }
        
        if data_type not in fetch_functions:
            raise ValueError(f"不支持的宏观数据类型: {data_type}")
        
        last_exception = None
        
        for attempt in range(DataResilient.MAX_RETRIES):
            try:
                RequestLimiter.acquire()
                
                df = fetch_functions[data_type]()
                
                if df is None:
                    df = pd.DataFrame()
                
                return df
                
            except Exception as e:
                last_exception = e
                if attempt < DataResilient.MAX_RETRIES - 1:
                    delay = min(DataResilient.BASE_DELAY * (2 ** attempt) + random.uniform(0, 1), DataResilient.MAX_DELAY)
                    print(f"重试获取 {data_type} 数据 (第{attempt + 1}次) - 延迟 {delay:.1f}秒...")
                    time.sleep(delay)
                else:
                    print(f"获取 {data_type} 数据失败: {str(e)}")
                    return pd.DataFrame()
        
        return pd.DataFrame()
    
    @staticmethod
    def get_stock_info(use_cache: bool = True) -> pd.DataFrame:
        cache_key = 'stock_info'
        
        if use_cache:
            cached_data = CacheManager.load_macro_cache(cache_key)
            if cached_data is not None:
                return cached_data
        
        for attempt in range(DataResilient.MAX_RETRIES):
            try:
                RequestLimiter.acquire()
                df = ak.stock_info_a_code_name()
                
                if use_cache and df is not None and not df.empty:
                    CacheManager.save_macro_cache(cache_key, df)
                
                return df
            except Exception as e:
                if attempt < DataResilient.MAX_RETRIES - 1:
                    delay = min(DataResilient.BASE_DELAY * (2 ** attempt), DataResilient.MAX_DELAY)
                    print(f"重试获取股票信息 (第{attempt + 1}次) - 延迟 {delay:.1f}秒...")
                    time.sleep(delay)
                else:
                    print(f"获取股票信息失败: {str(e)}")
                    return pd.DataFrame()
        
        return pd.DataFrame()
    
    @staticmethod
    def get_hs300_symbols(use_cache: bool = True) -> list:
        cache_key = 'hs300_symbols'
        
        if use_cache:
            cached_data = CacheManager.load_macro_cache(cache_key)
            if cached_data is not None:
                return cached_data
        
        for attempt in range(DataResilient.MAX_RETRIES):
            try:
                RequestLimiter.acquire()
                hs300 = ak.index_stock_cons(symbol="000300")
                hs300 = hs300.drop_duplicates(subset=['品种代码'], keep='first')
                hs300['symbol'] = hs300['品种代码'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(6)
                hs300['symbol'] = hs300['symbol'].apply(lambda x: f"{x}.SZ" if x.startswith(('0','3')) else f"{x}.SH")
                symbols = hs300['symbol'].drop_duplicates().tolist()
                
                if use_cache:
                    CacheManager.save_macro_cache(cache_key, symbols)
                
                return symbols
            except Exception as e:
                if attempt < DataResilient.MAX_RETRIES - 1:
                    delay = min(DataResilient.BASE_DELAY * (2 ** attempt), DataResilient.MAX_DELAY)
                    print(f"重试获取沪深300成分股 (第{attempt + 1}次) - 延迟 {delay:.1f}秒...")
                    time.sleep(delay)
                else:
                    print(f"获取沪深300成分股失败: {str(e)}")
                    return []
        
        return []