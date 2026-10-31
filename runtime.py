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
    for field, default in [('persona','personality.md'),('slang','internet-slang.md')]:
        value=Path(cfg.get(field,default))
        cfg[field]=str(value if value.is_absolute() else base/value)
    if cfg.get('api_key_file'):
        value=Path(cfg['api_key_file'])
        cfg['api_key_file']=str(value if value.is_absolute() else base/value)
    if cfg.get('endpoint'):
        from model_config import normalize_endpoint
        cfg['endpoint']=normalize_endpoint(cfg['endpoint'])
    vision = dict(cfg.get('vision', {}))
    vision['allowed_roots'] = [
        str(Path(value) if Path(value).is_absolute() else base / value)
        for value in vision.get('allowed_roots', ['conversations'])
    ]
    vision.setdefault('mode','native')
    if vision['mode']!='native':
        raise ValueError('vision.mode 必须为 native；纯文本接口请关闭 vision.enabled。')
    cfg['vision'] = vision
    if not isinstance(cfg.get('self_names'), list) or not cfg['self_names']:
        raise ValueError('self_names 至少需要填写一个机器人自己的 QQ 昵称。')
    return cfg


def api_headers(cfg):
    if cfg.get('api_key_file'):
        from model_config import read_secret
        path=Path(cfg['api_key_file'])
        if not path.is_absolute():path=ROOT/path
        return {'Authorization':'Bearer '+read_secret(path,cfg['endpoint'])}
    name = cfg.get('api_key_env', '')
    value = os.environ.get(name, '') if name else ''
    if name and not value and os.name=='nt':
        # Scheduled tasks may inherit an older environment. Read the current user's setting.
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as handle:
                value,_=winreg.QueryValueEx(handle,name)
        except (OSError,ImportError):
            value=''
    return {'Authorization': 'Bearer ' + value} if value else {}


def chat_payload(cfg, messages, profile):
    parameter=cfg.get('output_token_parameter','max_tokens')
    if parameter not in ('max_tokens','max_completion_tokens'):
        raise ValueError('output_token_parameter 不支持该字段')
    payload=dict(model=cfg['model'],messages=messages)
    payload[parameter]=profile['max_tokens']
    if cfg.get('temperature',.7) is not None:
        payload['temperature']=cfg.get('temperature',.7)
    from model_config import reasoning_protocol
    protocol=reasoning_protocol(cfg)
    if protocol in ('effort','strata'):
        payload['reasoning_effort']=profile['effort']
    if protocol=='strata' and profile['effort']!='none':
        payload['reasoning_budget_tokens']=profile['reasoning_budget_tokens']
    return payload
