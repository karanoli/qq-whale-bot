"""One read -> model -> send/ack cycle; can actually post to the configured QQ target."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runtime import load_config,api_headers
def cli(*arguments):
    result=subprocess.run([sys.executable,str(ROOT/"bridge.py"),*arguments],
                          cwd=ROOT,capture_output=True,text=True,encoding="utf-8")
    try:value=json.loads(result.stdout)
    except ValueError:raise RuntimeError("bridge没有返回JSON："+result.stderr[-500:])
    if result.returncode:raise RuntimeError(json.dumps(value,ensure_ascii=False))
    return value
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scope",required=True);p.add_argument("--images",action="store_true")
    args=p.parse_args()
    command=["read","--scope",args.scope]+(["--images"] if args.images else [])
    batch=cli(*command);pending=batch["pending_ids"]
    if not pending:
        print("没有新pending（首次读取只建基线），未调用模型。");return
    payload=cli("prompt","--scope",args.scope);cfg=load_config()
    with requests.Session() as session:
        session.trust_env=cfg.get("trust_env",False)
        r=session.post(cfg["endpoint"],json=payload,headers=api_headers(cfg),timeout=(8,600))
        r.raise_for_status();choice=r.json()["choices"][0]
    if choice.get("finish_reason")=="length":raise RuntimeError("回复截断，未发送，pending保留")
    text=re.sub(r"<think>.*?</think>","",choice["message"].get("content") or "",flags=re.S).strip()
    if text=="<NO_REPLY>":result=cli("ack","--scope",args.scope,"--ids",*pending)
    else:result=cli("send","--scope",args.scope,"--reply-to",*pending,"--text",text)
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
