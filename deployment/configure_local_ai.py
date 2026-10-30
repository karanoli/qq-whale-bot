"""Generate a native Strata profile without changing QQ targets or persona."""
import json
from pathlib import Path
from install_local_ai import REPO, read_json, atomic

def configure(ai_root, source, python, exe, pack, apply_bot=False, repo=REPO):
    repo=Path(repo); lock=read_json(repo/"deployment/models.lock.json"); model=lock["model"]
    state=repo/".local-ai"; logs=state/"logs"; logs.mkdir(parents=True,exist_ok=True)
    cfg=dict(exe=str(exe),cwd=str(source),tokenizer=str(pack/"tokenizer"),
             model_name=model["alias"],arch="deepseek41",host="127.0.0.1",port=model["port"],
             open_browser=False,engine_ready_s=3600,gpu=0,gpus_asked=True,
             lib_dirs=[str(exe.parent)],log=str(logs/"chat-engine.log"),
             args=["--pack",str(pack),"--max-context",str(model["context"]),"--eos","1",
                   "--dspark","auto","--dspark-conf","0.65","--experts",str(model["experts"]),"--vision","on"])
    cfg["args_written"]=cfg["args"][:]
    atomic(state/"chat.local.json",cfg)
    atomic(state/"services.local.json",dict(strata_python=str(python),strata_server=str(source/"serve/server.py"),
           strata_cwd=str(source),chat_port=model["port"],ai_root=str(ai_root)))
    if apply_bot:
        target=repo/"config.json"
        base=read_json(target if target.exists() else repo/"config.example.json")
        if target.exists(): atomic(state/"bot-config.before-local-ai.json",base)
        base.update(endpoint="http://127.0.0.1:%d/v1/chat/completions"%model["port"],
                    model=model["alias"],api_key_env="",send_reasoning_parameters=True,
                    vision=dict(enabled=True,mode="native"))
        atomic(target,base)
    return cfg
