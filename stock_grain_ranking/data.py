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
        # 初始化股票代码名称映射
        try:
            stock_info = ak.stock_info_a_code_name()
            cls.stock_names = dict(zip(stock_info['code'], stock_info['name']))
        except Exception as e:
            print(f"股票代码加载失败: {e}")
            cls.stock_names = {}

        # 初始化宏观数据
        cls.load_macro_data()

    # 新增CPI空值处理
    @classmethod
    def load_macro_data(cls):
        try:
            cls.macro_data = {
                'cpi': cls._process_cpi_data(ak.macro_china_cpi() if not pd.DataFrame(ak.macro_china_cpi()).empty else pd.DataFrame()),
                'fx': ak.fx_spot_quote(),
                'pmi': ak.macro_china_pmi(),
                'gdp': ak.macro_china_gdp()
            }
            # 处理空的CPI数据
            if cls.macro_data['cpi'].empty:
                print("警告：CPI数据获取失败，使用默认值")
                cls.macro_data['cpi'] = pd.DataFrame({
                    '日期': [datetime.now().strftime("%Y年%m月")],
                    '全国-当月': [2.5]
                })
        except Exception as e:
            print(f"宏观数据加载失败: {str(e)}")
            cls.macro_data = pd.read_pickle('macro_backup.pkl')

    @staticmethod
    def _process_cpi_data(cpi_df):
        if not cpi_df.empty:
            cpi_df['日期'] = pd.to_datetime(cpi_df.iloc[:,0].str.extract(r'(\d{4}年\d{1,2}月)')[0], format='%Y年%m月')
            return cpi_df.sort_values('日期')
        return cpi_df

    @staticmethod
    def _safe_fetch_cpi():
        try:
            return ak.macro_china_cpi()
        except Exception as e:
            print(f"获取CPI数据失败: {e}")
            return pd.DataFrame()
