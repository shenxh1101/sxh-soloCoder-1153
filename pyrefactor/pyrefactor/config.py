import os
import yaml

DEFAULT_CONFIG = {
    "rules": {
        "long_function": {
            "enabled": True,
            "max_lines": 30,
        },
        "duplicate_code": {
            "enabled": True,
            "min_block_lines": 6,
            "similarity_threshold": 0.8,
            "max_comparisons": 5000,
        },
        "complex_condition": {
            "enabled": True,
            "max_depth": 3,
        },
        "temporary_field": {
            "enabled": True,
        },
    },
    "refactoring": {
        "auto_apply": False,
        "confirm_before_apply": True,
        "backup": True,
    },
    "ignore_patterns": [
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "env",
        ".tox",
        "node_modules",
        "*.pyc",
    ],
    "vcs": {
        "skip_untracked": True,
    },
    "output": {
        "report_format": "text",
        "report_path": None,
    },
}


def load_config(config_path=None):
    config = dict_deep_copy(DEFAULT_CONFIG)
    if config_path and os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
        deep_merge(config, user_config)
    return config


def dict_deep_copy(source):
    result = {}
    for key, value in source.items():
        if isinstance(value, dict):
            result[key] = dict_deep_copy(value)
        elif isinstance(value, list):
            result[key] = list(value)
        else:
            result[key] = value
    return result


def deep_merge(base, override):
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            deep_merge(base[key], value)
        else:
            base[key] = value


def is_rule_enabled(config, rule_name):
    rule_config = config.get("rules", {}).get(rule_name, {})
    return rule_config.get("enabled", False)