"""Model settings, list discovery and Windows-bound encrypted API credentials."""
import copy
import ctypes
import json
import hashlib
import os
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit

LEVELS=("none","low","medium","high")
DEFAULT_LIMITS={
 "none":dict(budget=0,max_tokens=512,timeout_seconds=180),
 "low":dict(budget=128,max_tokens=768,timeout_seconds=240),
 "medium":dict(budget=384,max_tokens=1152,timeout_seconds=300),
 "high":dict(budget=1536,max_tokens=2304,timeout_seconds=600),
}
def normalize_endpoint(value):
    value=value.strip()
    if "://" not in value:value="https://"+value
    u=urlsplit(value)
    if u.scheme not in ("http","https") or not u.hostname or u.username or u.password or u.fragment:
        raise ValueError("填写HTTP/HTTPS接口地址，Key单独填写，地址不能含登录信息或片段")
    host=u.hostname.lower()
    if ":" in host:host="["+host+"]"
    port=u.port
    netloc=host+(":"+str(port) if port and (u.scheme,port) not in (("http",80),("https",443)) else "")
    path=u.path.rstrip("/")
    if path.endswith("/models"):path=path[:-len("/models")]+"/chat/completions"
    elif not path.endswith("/chat/completions"):path=(path or "/v1")+"/chat/completions"
    return urlunsplit((u.scheme,netloc,path,u.query,""))
def model_list_url(endpoint):
    u=urlsplit(normalize_endpoint(endpoint))
    return urlunsplit((u.scheme,u.netloc,u.path[:-len("/chat/completions")]+"/models",u.query,""))
def reasoning_protocol(cfg):
    value=cfg.get("reasoning_api")
    if value is None:return "strata" if cfg.get("send_reasoning_parameters",False) else "off"
    if value not in ("off","effort","strata"):raise ValueError("未知思考参数格式")
    return value
def fetch_models(endpoint,headers=None,trust_env=False,session=None):
    import requests
    own=session is None;session=session or requests.Session()
    session.trust_env=trust_env
    try:
        try:r=session.get(model_list_url(endpoint),headers=headers or {},timeout=(8,20))
        except requests.RequestException as exc:raise ValueError("无法获取模型列表："+type(exc).__name__) from None
        if not r.ok:raise ValueError("模型列表返回HTTP %d；检查地址、Key及账户权限"%r.status_code)
        try:data=r.json()
        except ValueError:raise ValueError("模型列表没有返回JSON，可手动填写模型ID") from None
        rows=data.get("data") if isinstance(data,dict) else None
        if not isinstance(rows,list):raise ValueError("不兼容的模型列表格式，可手动填写模型ID")
        names=sorted({row["id"].strip() for row in rows if isinstance(row,dict) and isinstance(row.get("id"),str) and row["id"].strip()})
        if not names:raise ValueError("返回的模型列表为空，可手动填写模型ID")
        return names
    finally:
        if own:session.close()
def _crypt(data,decrypt=False):
    if os.name!="nt":raise RuntimeError("密钥加密存储仅支持Windows；其他平台可用环境变量")
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_=[("size",wintypes.DWORD),("data",ctypes.POINTER(ctypes.c_ubyte))]
    buf=ctypes.create_string_buffer(data);incoming=Blob(len(data),ctypes.cast(buf,ctypes.POINTER(ctypes.c_ubyte)));out=Blob()
    crypt=ctypes.WinDLL("crypt32",use_last_error=True)
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    fn=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    fn.restype=wintypes.BOOL
    if not fn(ctypes.byref(incoming),None,None,None,None,1,ctypes.byref(out)):raise ctypes.WinError(ctypes.get_last_error())
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    try:return ctypes.string_at(out.data,out.size)
    finally:kernel.LocalFree(out.data)
def write_secret(path,key,endpoint):
    raw=json.dumps(dict(key=key,endpoint=normalize_endpoint(endpoint)),ensure_ascii=False).encode("utf-8")
    encrypted=_crypt(raw)
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+".tmp");temp.write_bytes(encrypted);os.replace(temp,path)
def read_secret(path,endpoint):
    value=json.loads(_crypt(Path(path).read_bytes(),decrypt=True).decode("utf-8"))
    if value.get("endpoint")!=normalize_endpoint(endpoint):raise ValueError("已保存密钥属于其他接口地址，请重新设置Key")
    key=value.get("key")
    if not isinstance(key,str) or not key:raise ValueError("已保存的密钥无效")
    return key
def preview_headers(original,endpoint,key,no_key):
    if no_key:return {}
    if key.strip():return {"Authorization":"Bearer "+key.strip()}
    if normalize_endpoint(original["endpoint"])!=normalize_endpoint(endpoint):
        raise ValueError("接口地址已改变，请输入该服务的Key，或勾选无需Key")
    from runtime import api_headers
    headers=api_headers(original)
    if not headers:raise ValueError("请输入API Key，或勾选无需Key")
    return headers
def settings_config(original,values):
    cfg=copy.deepcopy(original)
    cfg["endpoint"]=normalize_endpoint(values["endpoint"])
    model=values["model"].strip()
    if not model:raise ValueError("请从列表选择模型，或手动填写模型ID")
    cfg["model"]=model
    protocol=values["protocol"]
    if protocol not in ("off","effort","strata"):raise ValueError("请选择思考参数格式")
    level=values["level"]
    if level not in LEVELS:raise ValueError("请选择思考档位")
    cfg["reasoning_api"]=protocol;cfg["send_reasoning_parameters"]=protocol=="strata"
    policy=copy.deepcopy(cfg.get("reasoning",{}));policy.update(default=level,mode="auto" if values["auto"] else "fixed")
    for effort in LEVELS:
        current=dict(DEFAULT_LIMITS[effort]);current.update(values["limits"][effort])
        for name in ("budget","max_tokens","timeout_seconds"):
            try:current[name]=int(current[name])
            except (ValueError,TypeError):raise ValueError("预算、生成上限和超时必须是整数") from None
        if effort=="none":current["budget"]=0
        if not 0<=current["budget"]<=65536 or not 1<=current["max_tokens"]<=131072 or not 1<=current["timeout_seconds"]<=3600:
            raise ValueError("预算范围0～65536，生成上限1～131072，超时1～3600秒")
        if current["budget"]>=current["max_tokens"]:raise ValueError("思考预算必须小于总生成token上限")
        policy[effort]=current
    cfg["reasoning"]=policy
    cfg["vision"]=dict(cfg.get("vision",{}),enabled=bool(values["vision"]),mode="native")
    cfg["trust_env"]=bool(values["trust_env"])
    cfg["check_models"]=bool(values.get("check_models",cfg.get("check_models",True)))
    token=values.get("output_token_parameter","max_tokens")
    if token not in ("max_tokens","max_completion_tokens"):raise ValueError("生成上限字段不支持")
    cfg["output_token_parameter"]=token
    return cfg
def save_settings(path,values,key="",no_key=False,expected_bytes=None):
    path=Path(path);raw=path.read_bytes()
    if expected_bytes is not None and raw!=expected_bytes:raise ValueError("配置已被其他窗口修改，请重新打开设置")
    original=json.loads(raw.decode("utf-8-sig"))
    cfg=settings_config(original,values)
    # Validate old-key ownership before writing either file.
    credential_original=copy.deepcopy(original)
    if original.get("api_key_file"):
        secret=Path(original["api_key_file"])
        credential_original["api_key_file"]=str(secret if secret.is_absolute() else path.parent/secret)
    preview_headers(credential_original,cfg["endpoint"],key,no_key)
    if no_key:
        cfg["api_key_env"]="";cfg.pop("api_key_file",None)
    elif key.strip():
        digest=hashlib.sha256(cfg["endpoint"].encode()).hexdigest()[:16]
        secret=path.parent/(".secrets/model-api-"+digest+".dpapi")
        write_secret(secret,key.strip(),cfg["endpoint"])
        cfg["api_key_file"]=str(secret.relative_to(path.parent));cfg["api_key_env"]=""
    else:
        # Read the existing field from original so relative paths stay portable on disk.
        if original.get("api_key_file"):cfg["api_key_file"]=original["api_key_file"]
    temp=path.with_name(path.name+".tmp")
    temp.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding="utf-8");os.replace(temp,path)
    return cfg
