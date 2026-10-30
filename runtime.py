"""Portable configuration and request helpers; no desktop access on import."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_config(path=None):
    path = Path(path) if path is not None else ROOT / 'config.json'
    if not path.is_file():
        raise FileNotFoundError('缺少 config.json，请先运行 setup.cmd。')
    cfg = json.loads(path.read_text(encoding='utf-8-sig'))
    base = path.resolve().parent
    persona = Path(cfg.get('persona', 'personality.md'))
    cfg['persona'] = str(persona if persona.is_absolute() else base / persona)
    vision = dict(cfg.get('vision', {}))
    vision['allowed_roots'] = [
        str(Path(value) if Path(value).is_absolute() else base / value)
        for value in vision.get('allowed_roots', ['conversations'])
    ]
    cfg['vision'] = vision
    if not isinstance(cfg.get('self_names'), list) or not cfg['self_names']:
        raise ValueError('self_names 至少需要填写一个机器人自己的 QQ 昵称。')
    return cfg


def api_headers(cfg):
    name = cfg.get('api_key_env', '')
    value = os.environ.get(name, '') if name else ''
    return {'Authorization': 'Bearer ' + value} if value else {}


def chat_payload(cfg, messages, profile):
    payload = dict(model=cfg['model'], messages=messages,
                   temperature=cfg.get('temperature', .7),
                   max_tokens=profile['max_tokens'])
    if cfg.get('send_reasoning_parameters', False):
        payload.update(reasoning_effort=profile['effort'],
                       reasoning_budget_tokens=profile['reasoning_budget_tokens'])
    return payload
