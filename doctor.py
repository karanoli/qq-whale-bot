"""Read-only dependency and OpenAI-compatible model-list checks."""
import argparse
import importlib.util
import json
import sys
import urllib.request
from runtime import load_config,api_headers
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--services-only",action="store_true");args=p.parse_args()
    cfg=load_config();errors=[]
    if not args.services_only:
        if sys.platform!="win32":errors.append("桌面机器人仅支持Windows，Mac可运行核心测试。")
        for name in ["requests","win32gui","cv2","PIL","numpy","onnxruntime","rapidocr_onnxruntime","tkinter"]:
            if importlib.util.find_spec(name) is None:errors.append("缺少依赖："+name)
    endpoint=cfg["endpoint"]
    if not endpoint.endswith("/chat/completions"):errors.append("endpoint应是以/chat/completions结尾的完整地址。")
    elif cfg.get("check_models",True):
        try:
            url=endpoint[:-len("/chat/completions")]+"/models"
            request=urllib.request.Request(url,headers=api_headers(cfg))
            opener=urllib.request.build_opener() if cfg.get("trust_env") else urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request,timeout=8) as response:data=json.load(response)
            models=data.get("data",[])
            chosen=[m for m in models if m.get("id")==cfg["model"]]
            if not chosen:raise ValueError("model不在服务返回的模型列表中")
            modalities=chosen[0].get("architecture",{}).get("input_modalities")
            if cfg.get("vision",{}).get("enabled") and modalities is not None and "image" not in modalities:
                raise ValueError("服务声明该模型不支持图片")
            print("模型接口可访问，model匹配。"+("原生图片能力已由服务声明。" if modalities and "image" in modalities else ""))
        except Exception as exc:errors.append("模型检查失败："+type(exc).__name__+" "+str(exc))
    else:print("按check_models=false跳过模型列表检查；实际请求是否支持由服务端决定。")
    for error in errors:print(error)
    return 1 if errors else 0
if __name__=="__main__":
    try:sys.exit(main())
    except (OSError,ValueError,KeyError) as exc:print(str(exc));sys.exit(1)
