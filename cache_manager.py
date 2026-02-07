import pickle
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Any

class CacheManager:
    CACHE_DIR = Path("cache")
    STOCK_CACHE_DIR = CACHE_DIR / "stock"
    MACRO_CACHE_DIR = CACHE_DIR / "macro"
    CACHE_EXPIRE_HOURS = 24
    
    @classmethod
    def initialize(cls):
        cls.STOCK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cls.MACRO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def get_cache_key(cls, symbol: str, start_date: str, end_date: str) -> str:
        return f"{symbol}_{start_date}_{end_date}.pkl"
    
    @classmethod
    def get_stock_cache_path(cls, symbol: str, start_date: str, end_date: str) -> Path:
        cache_key = cls.get_cache_key(symbol, start_date, end_date)
        return cls.STOCK_CACHE_DIR / cache_key
    
    @classmethod
    def get_macro_cache_path(cls, data_type: str) -> Path:
        return cls.MACRO_CACHE_DIR / f"{data_type}.pkl"
    
    @classmethod
    def is_cache_valid(cls, cache_path: Path) -> bool:
        if not cache_path.exists():
            return False
        
        cache_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
        expire_time = timedelta(hours=cls.CACHE_EXPIRE_HOURS)
        
        return datetime.now() - cache_time < expire_time
    
    @classmethod
    def load_stock_cache(cls, symbol: str, start_date: str, end_date: str) -> Optional[Any]:
        cache_path = cls.get_stock_cache_path(symbol, start_date, end_date)
        
        if not cls.is_cache_valid(cache_path):
            return None
        
        try:
            with open(cache_path, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            print(f"加载缓存失败 {cache_path}: {str(e)}")
            return None
    
    @classmethod
    def save_stock_cache(cls, symbol: str, start_date: str, end_date: str, data: Any):
        cache_path = cls.get_stock_cache_path(symbol, start_date, end_date)
        
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            print(f"保存缓存失败 {cache_path}: {str(e)}")
    
    @classmethod
    def load_macro_cache(cls, data_type: str) -> Optional[Any]:
        cache_path = cls.get_macro_cache_path(data_type)
        
        if not cls.is_cache_valid(cache_path):
            return None
        
        try:
            with open(cache_path, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            print(f"加载宏观数据缓存失败 {cache_path}: {str(e)}")
            return None
    
    @classmethod
    def save_macro_cache(cls, data_type: str, data: Any):
        cache_path = cls.get_macro_cache_path(data_type)
        
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            print(f"保存宏观数据缓存失败 {cache_path}: {str(e)}")
    
    @classmethod
    def clear_expired_cache(cls):
        now = datetime.now()
        expire_time = timedelta(hours=cls.CACHE_EXPIRE_HOURS)
        
        for cache_dir in [cls.STOCK_CACHE_DIR, cls.MACRO_CACHE_DIR]:
            if not cache_dir.exists():
                continue
            
            for cache_file in cache_dir.glob("*.pkl"):
                cache_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
                if now - cache_time >= expire_time:
                    try:
                        cache_file.unlink()
                        print(f"删除过期缓存: {cache_file}")
                    except Exception as e:
                        print(f"删除缓存失败 {cache_file}: {str(e)}")
    
    @classmethod
    def clear_all_cache(cls):
        for cache_dir in [cls.STOCK_CACHE_DIR, cls.MACRO_CACHE_DIR]:
            if cache_dir.exists():
                for cache_file in cache_dir.glob("*.pkl"):
                    try:
                        cache_file.unlink()
                    except Exception as e:
                        print(f"删除缓存失败 {cache_file}: {str(e)}")
        
        print("已清空所有缓存")
    
    @classmethod
    def get_cache_stats(cls) -> dict:
        stats = {
            'stock_cache_count': 0,
            'macro_cache_count': 0,
            'total_size_mb': 0
        }
        
        if cls.STOCK_CACHE_DIR.exists():
            stats['stock_cache_count'] = len(list(cls.STOCK_CACHE_DIR.glob("*.pkl")))
        
        if cls.MACRO_CACHE_DIR.exists():
            stats['macro_cache_count'] = len(list(cls.MACRO_CACHE_DIR.glob("*.pkl")))
        
        total_size = 0
        for cache_dir in [cls.STOCK_CACHE_DIR, cls.MACRO_CACHE_DIR]:
            if cache_dir.exists():
                for cache_file in cache_dir.glob("*.pkl"):
                    total_size += cache_file.stat().st_size
        
        stats['total_size_mb'] = round(total_size / (1024 * 1024), 2)
        
        return stats