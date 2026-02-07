import pandas as pd
import akshare as ak
from datetime import datetime, timedelta

class DataFetcher:
    @staticmethod
    def get_hs300_symbols():
        """获取沪深300成分股代码（与stockRanking.py保持完全一致）"""
        try:
            hs300 = ak.index_stock_cons(symbol="000300")
            hs300 = hs300.drop_duplicates(subset=['品种代码'], keep='first')
            hs300['symbol'] = hs300['品种代码'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(6)
            hs300['symbol'] = hs300['symbol'].apply(lambda x: f"{x}.SZ" if x.startswith(('0','3')) else f"{x}.SH")
            return hs300['symbol'].drop_duplicates().tolist()
        except Exception as e:
            print(f"获取沪深300成分股失败: {str(e)}")
            return []
            
    @staticmethod
    def fetch_stock_data(symbol, start_date, end_date):
        """通过AKShare获取股票历史数据（日线）"""
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date.strftime("%Y%m%d"), end_date=end_date.strftime("%Y%m%d"))
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

class DataCache:
    macro_data = {}
    stock_names = {}

    @classmethod
    def initialize(cls):
        # 初始化股票代码名称映射
        try:
            # 预先获取宏观数据（每日仅更新一次）
            DataCache.macro_data = {
                'cpi': ak.macro_china_cpi() if not pd.DataFrame(ak.macro_china_cpi()).empty else pd.DataFrame(),
                'fx': ak.fx_spot_quote(),
                'pmi': ak.macro_china_pmi(),
                'gdp': ak.macro_china_gdp() if not pd.DataFrame(ak.macro_china_gdp()).empty else pd.DataFrame()
            }
            
            # 处理空的CPI数据情况
            if DataCache.macro_data['cpi'].empty:
                print("警告：CPI数据获取失败，使用默认值")
                DataCache.macro_data['cpi'] = pd.DataFrame({
                    '日期': [datetime.now().strftime("%Y年%m月")],
                    '全国-当月': [2.5]
                })
            
            # 转换CPI日期格式
            cpi_df = DataCache.macro_data['cpi']
            # 检查是否存在'统计对象'列
            if '日期' in cpi_df.columns:
                cpi_df['日期'] = pd.to_datetime(cpi_df['日期'], errors='coerce')
            elif '统计时间' in cpi_df.columns:
                cpi_df['日期'] = pd.to_datetime(cpi_df['统计时间'], format='%Y年%m月')
            else:
                cpi_df['日期'] = pd.to_datetime(cpi_df.iloc[:,0].str.extract(r'(\d{4}年\d{1,2}月)')[0], format='%Y年%m月', errors='coerce')
                print('警告：使用第一列数据进行日期解析')
            
            # 处理GDP季度格式
            gdp_df = DataCache.macro_data['gdp']
            gdp_df['季度日期'] = gdp_df['季度'].apply(lambda x: pd.Timestamp(year=int(x.split('年')[0]), 
                month=(int(x.split('第')[1][0])*3-2), day=1))
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
                'cpi': cls._process_cpi_data(ak.macro_china_cpi()) if ak.macro_china_cpi() is not None else pd.DataFrame({'统计时间': [datetime.now().strftime('%Y年%m月')], '全国-当月': [2.5]}),
                'fx': ak.fx_spot_quote(),
                'pmi': ak.macro_china_pmi(),
                'gdp': ak.macro_china_gdp() if ak.macro_china_gdp() is not None else pd.DataFrame({'季度': ['2023年第4季度'], '国内生产总值-同比增长': [4.5], '国内生产总值-绝对值': [1260582]})
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
            # 加载本地备份数据（需要提前准备）
            # 生成默认宏观数据
            cls.macro_data = {
                'cpi': pd.DataFrame({'统计时间': [datetime.now().strftime('%Y年%m月')], '全国-当月': [2.5]}),
                'fx': pd.DataFrame(),
                'pmi': pd.DataFrame(),
                'gdp': pd.DataFrame()
            }

    @staticmethod
    def _process_cpi_data(cpi_df):
        # 从缓存获取数据
        cpi_df = DataCache.macro_data['cpi']
        
        # 转换为季度和月份用于宏观数据对齐
        current_date = datetime.now()
        quarter = (current_date.month - 1) // 3 + 1
        # 动态识别日期列
        date_column = '日期' if '日期' in cpi_df.columns else '统计时间' if '统计时间' in cpi_df.columns else cpi_df.columns[0]
        cpi_df['processed_date'] = pd.to_datetime(cpi_df[date_column], errors='coerce')
        cpi_mask = (cpi_df['processed_date'] >= current_date - pd.DateOffset(months=3)) & (cpi_df['processed_date'] <= current_date)
        cpi_current = cpi_df[cpi_mask].iloc[-1]['全国-当月'] if any(cpi_mask) else None
        if not cpi_current:
            print(f"CPI数据异常：当前日期{current_date.strftime('%Y-%m-%d')} 最近可用数据日期{cpi_df['日期'].max().strftime('%Y-%m-%d')}")
            return 0.10

    @staticmethod
    def _safe_fetch_cpi():
        try:
            return ak.macro_china_cpi()
        except Exception as e:
            print(f"获取CPI数据失败: {e}")
            return pd.DataFrame()
