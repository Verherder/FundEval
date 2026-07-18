import os
import re
import tempfile
from pathlib import Path
from typing import Any, Optional, Dict

import yaml


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
MAX_FUND_REFRESH_BATCH_SIZE = 15


def get_config_path(config_path: Optional[str] = None) -> Path:
    if config_path:
        return Path(config_path)

    explicit = os.getenv("FUNDEVAL_CONFIG")
    if explicit:
        return Path(explicit)

    cwd = Path.cwd()
    for path in [cwd / "config.yaml", _PROJECT_ROOT / "config.yaml"]:
        if path.exists():
            return path
    raise FileNotFoundError("config.yaml not found")


def load_yaml_config(config_path: Optional[str] = None) -> dict:
    path = get_config_path(config_path)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _update_yaml_section_values(content: str, section: str, values: Dict[str, Any]) -> str:
    lines = content.splitlines(keepends=True)
    section_index = next((i for i, line in enumerate(lines) if line.rstrip() == f"{section}:"), None)
    if section_index is None:
        suffix = "" if not content or content.endswith("\n") else "\n"
        rendered = "".join(f"  {key}: {str(value).lower() if isinstance(value, bool) else value}\n" for key, value in values.items())
        return f"{content}{suffix}{section}:\n{rendered}"

    section_end = len(lines)
    for index in range(section_index + 1, len(lines)):
        stripped = lines[index].strip()
        if stripped and not lines[index].startswith((" ", "\t", "#")):
            section_end = index
            break

    missing = dict(values)
    for index in range(section_index + 1, section_end):
        for key, value in list(missing.items()):
            match = re.match(
                rf"^(\s*{re.escape(key)}\s*:\s*)[^#\r\n]*?([ \t]*#.*)?(?:\r?\n)?$",
                lines[index],
            )
            if not match:
                continue
            rendered = str(value).lower() if isinstance(value, bool) else str(value)
            newline = "\n" if lines[index].endswith("\n") else ""
            suffix = match.group(2) or ""
            lines[index] = f"{match.group(1)}{rendered}{suffix}{newline}"
            missing.pop(key)
            break

    for key, value in reversed(list(missing.items())):
        rendered = str(value).lower() if isinstance(value, bool) else str(value)
        lines.insert(section_index + 1, f"  {key}: {rendered}\n")
    return "".join(lines)


def save_refresh_settings(auto_refresh_enabled: bool, auto_refresh_interval: int, request_batch_size: int) -> dict:
    path = get_config_path()
    content = path.read_text(encoding="utf-8")
    updated_content = _update_yaml_section_values(
        content,
        "page_refresh",
        {
            "auto_refresh_enabled": bool(auto_refresh_enabled),
            "auto_refresh_interval": int(auto_refresh_interval),
        },
    )
    updated_content = _update_yaml_section_values(
        updated_content,
        "fund_refresh",
        {"request_batch_size": int(request_batch_size)},
    )
    yaml.safe_load(updated_content)

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as temp_file:
            temp_file.write(updated_content)
            temp_path = Path(temp_file.name)
        os.replace(temp_path, path)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()

    return get_refresh_settings()


def get_page_refresh_config() -> Dict[str, int]:
    try:
        config = load_yaml_config()
        page_refresh = config.get('page_refresh', {})
        return {
            'auto_refresh_enabled': page_refresh.get('auto_refresh_enabled', True) is not False,
            'auto_refresh_interval': page_refresh.get('auto_refresh_interval', 60000)
        }
    except Exception as e:
        import logging
        logging.warning(f"Failed to load page_refresh config: {e}, using defaults")
        return {
            'auto_refresh_enabled': True,
            'auto_refresh_interval': 60000
        }


def _positive_int(value: Any, default: int) -> int:
    try:
        normalized = int(value)
        if normalized > 0:
            return normalized
    except (TypeError, ValueError):
        pass
    return default


def get_fund_refresh_config() -> Dict[str, int]:
    try:
        config = load_yaml_config()
        fund_refresh = config.get('fund_refresh', {})
        return {
            'request_batch_size': min(
                _positive_int(fund_refresh.get('request_batch_size'), 5),
                MAX_FUND_REFRESH_BATCH_SIZE,
            )
        }
    except Exception as e:
        import logging
        logging.warning(f"Failed to load fund_refresh config: {e}, using defaults")
        return {
            'request_batch_size': 5
        }


def get_refresh_settings() -> Dict[str, Any]:
    return {**get_page_refresh_config(), **get_fund_refresh_config()}


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
