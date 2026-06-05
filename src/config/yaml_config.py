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
    'fundgz_js_tpl',
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

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # project root


def load_yaml_config(config_path: Optional[str] = None) -> dict:
    if config_path:
        path = Path(config_path)
    else:
        import os

        explicit = os.getenv("FUNDEVAL_CONFIG")
        if explicit:
            path = Path(explicit)
        else:
            cwd = Path.cwd()
            for p in [cwd / "config.yaml", _PROJECT_ROOT / "config.yaml"]:
                if p.exists():
                    path = p
                    break
            else:
                raise FileNotFoundError("config.yaml not found")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_page_refresh_config() -> Dict[str, int]:
    try:
        config = load_yaml_config()
        page_refresh = config.get('page_refresh', {})
        return {
            'auto_refresh_interval': page_refresh.get('auto_refresh_interval', 60000)
        }
    except Exception as e:
        import logging
        logging.warning(f"Failed to load page_refresh config: {e}, using defaults")
        return {
            'auto_refresh_interval': 60000
        }


def get_data_source_urls() -> Dict[str, str]:
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


def get_performance_chart_config() -> Dict[str, Any]:
    try:
        config = load_yaml_config()
        pc = config.get('performance_chart', {})
        return {
            'interval_labels': pc.get('interval_labels', {}),
            'interval_days': pc.get('interval_days', {}),
            'interval_order': pc.get('interval_order', []),
            'default_interval': pc.get('default_interval', 'SINCE_ESTABLISHMENT'),
            'default_profit_interval': pc.get('default_profit_interval', 'THREE_MONTH'),
        }
    except Exception:
        return {}


def get_nav_sync_config() -> Dict[str, Any]:
    try:
        config = load_yaml_config()
        ns = config.get('nav_sync', {})
        return {
            'request_page_size': ns.get('request_page_size', 300),
            'backfill_months': ns.get('backfill_months', 12),
            'include_today_after': ns.get('include_today_after', '20:00'),
        }
    except Exception:
        return {}


def get_server_config() -> Dict[str, Any]:
    try:
        config = load_yaml_config()
        return config.get('server', {})
    except Exception:
        return {}
