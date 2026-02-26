import yaml
from pathlib import Path
from typing import Any, Optional

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
