"""JSON command-line adapter. Desktop commands use the same verified QQ transport."""
import argparse
import contextlib
import json
from pathlib import Path
import sys
from runtime import ROOT,load_config,chat_payload
from memory import Memory,targets,key
from reasoning import choose

def output(value):
    print(json.dumps(value,ensure_ascii=False),flush=True)
def target_for(scope):
    found=[t for t in targets() if key(t)==scope]
    if len(found)!=1:raise ValueError("scope必须来自targets.json")
    return found[0]
def envelope(memory,baseline=False):
    return dict(schema_version=1,scope=memory.key,target=memory.target,baseline=baseline,
                timestamp_semantics="first_observed_not_original_send_time",
                pending_ids=list(memory.data["pending"]),messages=memory.data["messages"])
def request_for(memory,cfg):
    from native_vision import context,system_prompt,fresh_rows
    profile=choose(memory,cfg)
    messages,meta=context(memory,limit=1500 if profile["effort"]=="high" else 2400,
                          enable_images=cfg.get("vision",{}).get("enabled",False))
    persona=Path(cfg["persona"]).read_text(encoding="utf-8")
    slang=Path(cfg["slang"]).read_text(encoding="utf-8")[:2200]
    has_images=any(r.get("image_count") or r.get("images") for r in fresh_rows(memory))
    system=system_prompt(persona,slang,memory.target,has_images)
    return chat_payload(cfg,[dict(role="system",content=system)]+messages,profile)
@contextlib.contextmanager
def exclusive_desktop():
    if sys.platform!="win32":raise RuntimeError("QQ桌面操作仅支持Windows")
    import win32event,win32api,winerror
    handles=[]
    for name in ["Local\\AIchatVisualBot","Local\\QQWhaleBot"]:
        handle=win32event.CreateMutex(None,False,name)
        if win32api.GetLastError()==winerror.ERROR_ALREADY_EXISTS:
            handle.Close()
            for held in handles:held.Close()
            raise RuntimeError("请先停止旧版/当前机器人；桌面正被占用")
        handles.append(handle)
    stop=ROOT/"STOP";saved=stop.read_bytes() if stop.exists() else None
    try:
        if saved is not None:stop.unlink()
        yield
    finally:
        if saved is not None and not stop.exists():stop.write_bytes(saved)
        for held in handles:held.Close()
def validate_reply(text,cfg):
    from reply_text import clean_reply
    text=clean_reply(text)
    if not text or len(text)>cfg.get("max_reply_chars",240):raise ValueError("回复为空或超过长度限制")
    if "NO_REPLY" in text.upper():raise ValueError("静默标记不能发到QQ；请用ack")
    return text
def run(args):
    if args.command=="targets":output(dict(schema_version=1,targets=targets()));return 0
    cfg=load_config();target=target_for(args.scope)
    if args.command=="prompt":
        output(request_for(Memory(target),cfg));return 0
    with exclusive_desktop():
        m=Memory(target)
        m.data["bot_names"]=list(dict.fromkeys(m.data["bot_names"]+cfg["self_names"]))
        if args.command=="ack":
            ids=set(args.ids)
            if not ids.issubset(set(m.data["pending"])):raise ValueError("ids包含非pending消息")
            m.data["pending"]=[i for i in m.data["pending"] if i not in ids];m.save()
            output(dict(ok=True,scope=m.key,acknowledged=list(args.ids)));return 0
        from transport import Transport
        t=Transport(dict(cfg,target=target))
        if args.command=="read":
            rows=t.collect()
            baseline=not m.data["initialized"] or m.data.get("reader_version")!="uia-1" or getattr(t,"read_baseline",False)
            m.merge(rows,baseline=baseline)
            if baseline:m.data["pending"]=[];m.data["reader_version"]="uia-1"
            if args.images:
                from vision import Vision
                Vision(cfg).enrich(m,t)
            m.save();output(envelope(m,baseline));return 0
        text=validate_reply(args.text,cfg);replying=args.reply_to or []
        if not set(replying).issubset(set(m.data["pending"])):raise ValueError("reply-to包含非pending消息")
        attempted=False
        def attempt():
            nonlocal attempted
            m.record_attempt(text,replying);attempted=True
        try:
            rows=t.send(text,on_attempt=attempt);m.remember_sent(rows,text)
        except Exception as exc:
            output(dict(ok=False,scope=m.key,delivery="uncertain" if attempted else "not_attempted",
                        retry_safe=not attempted,error=type(exc).__name__+": "+str(exc)))
            return 2
        output(dict(ok=True,scope=m.key,delivery="confirmed",text=text,reply_to=replying));return 0
def main():
    p=argparse.ArgumentParser(description=__doc__)
    commands=p.add_subparsers(dest="command",required=True)
    commands.add_parser("targets")
    for command in ["read","prompt","send","ack"]:
        sub=commands.add_parser(command);sub.add_argument("--scope",required=True)
        if command=="read":sub.add_argument("--images",action="store_true")
        if command=="send":
            sub.add_argument("--text",required=True);sub.add_argument("--reply-to",nargs="+")
        if command=="ack":sub.add_argument("--ids",nargs="+",required=True)
    args=p.parse_args()
    try:return run(args)
    except Exception as exc:output(dict(ok=False,error=type(exc).__name__+": "+str(exc)));return 1
if __name__=="__main__":sys.exit(main())
