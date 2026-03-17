import yaml
from pathlib import Path
from typing import Any, Optional, Dict


REQUIRED_DATA_SOURCE_URL_KEYS = [
    # fund123
    'fund123_origin',
    'fund123_fund_page',
    'fund123_search_api',
    'fund123_matiaria_tpl',
    'fund123_curves_api',
    'fund123_intraday_api',
    'fund123_history_net_value_api',
    # baidu
    'gushitong_origin',
    'gushitong_referer',
    'baidu_index_warmup',
    'baidu_getbanner_tpl',
    'baidu_getquotation_api',
    'baidu_expressnews_tpl',
    'baidu_metrictrend_api',
    # eastmoney
    'eastmoney_fundguide_api',
    'eastmoney_fundguide_referer',
    'eastmoney_bk_api',
    # jijinhao / cngold
    'cngold_hist_referer',
    'cngold_realtime_referer',
    'jijinhao_history_api',
    'jijinhao_realtime_api',
]

def load_yaml_config(config_path: Optional[str] = None) -> dict:
    """
    加载 YAML 配置文件，返回配置字典。
    优先级：环境变量 FUNDEVAL_CONFIG > 当前目录 > 项目根目录
    """
    if config_path:
        path = Path(config_path)
    else:
        import os
        explicit = os.getenv("FUNDEVAL_CONFIG")
        if explicit:
            path = Path(explicit)
        else:
            cwd = Path.cwd()
            for p in [cwd / "config.yaml", Path(__file__).resolve().parent.parent / "config.yaml"]:
                if p.exists():
                    path = p
                    break
            else:
                raise FileNotFoundError("config.yaml not found")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_page_refresh_config() -> Dict[str, int]:
    """
    获取页面刷新配置（从config.yaml）
    返回：{
        'auto_refresh_interval': 毫秒
    }
    """
    try:
        config = load_yaml_config()
        page_refresh = config.get('page_refresh', {})
        return {
            'auto_refresh_interval': page_refresh.get('auto_refresh_interval', 60000)
        }
    except Exception as e:
        # 返回默认值
        import logging
        logging.warning(f"Failed to load page_refresh config: {e}, using defaults")
        return {
            'auto_refresh_interval': 60000
        }


def get_data_source_urls() -> Dict[str, str]:
    """获取数据源URL配置（单一来源：config.yaml）。"""
    config = load_yaml_config()
    configured = config.get('data_sources', {}).get('urls', {})

    if not isinstance(configured, dict):
        raise ValueError("config.yaml 中 data_sources.urls 必须是字典")

    missing_keys = [
        key for key in REQUIRED_DATA_SOURCE_URL_KEYS
        if not isinstance(configured.get(key), str) or not configured.get(key).strip()
    ]
    if missing_keys:
        raise ValueError(f"config.yaml 缺少必要的数据源URL配置: {', '.join(missing_keys)}")

    return {key: configured[key].strip() for key in REQUIRED_DATA_SOURCE_URL_KEYS}
