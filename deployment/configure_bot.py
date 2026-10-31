"""Apply explicit install options, keeping target lists/persona untouched."""
import argparse
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument("--qq-name");p.add_argument("--endpoint");p.add_argument("--model");p.add_argument("--api-mode",action="store_true");a=p.parse_args()
    path=ROOT/"config.json";cfg=json.loads(path.read_text(encoding="utf-8-sig"))
    if a.qq_name:cfg["self_names"]=[a.qq_name]
    if a.endpoint:cfg["endpoint"]=a.endpoint
    if a.model:cfg["model"]=a.model
    if a.api_mode:cfg.update(api_key_env=cfg.get("api_key_env") or "QQ_BOT_API_KEY",reasoning_api="off",send_reasoning_parameters=False,vision=dict(enabled=False,mode="native"))
    if a.api_mode:cfg.pop("api_key_file",None)
    path.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding="utf-8")
if __name__=="__main__":main()
