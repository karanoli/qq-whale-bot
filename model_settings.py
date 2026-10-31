"""Standalone model and reasoning settings. It never operates the QQ desktop."""
import argparse
import ctypes
import os
import copy
import json
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk,messagebox
from urllib.parse import urlsplit
from runtime import ROOT,load_config,api_headers
from model_config import (LEVELS,DEFAULT_LIMITS,normalize_endpoint,reasoning_protocol,
                          fetch_models,preview_headers,save_settings)

PROTOCOLS={"兼容模式（不发送思考参数）":"off","通用 effort（服务需支持）":"effort","本地 Strata（程度＋预算）":"strata"}
LEVEL_LABELS={"关闭思考":"none","低":"low","中":"medium","高":"high"}
class ModelSettings:
    def __init__(self,config_path=None,on_close=None):
        self.on_close=on_close
        self.path=Path(config_path or ROOT/"config.json")
        self.original=self.path.read_bytes();self.cfg=load_config(self.path)
        if os.name=="nt":
            try:ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
            except (AttributeError,OSError):pass
        self.root=tk.Tk();self.root.title("小鲸 · 模型与思考设置");self.root.geometry("920x680");self.root.minsize(800,540)
        if os.name=="nt":self.root.attributes("-topmost",True)
        self.queue=queue.Queue();self.closed=False;self.busy=False
        self.endpoint=tk.StringVar(value=self.cfg["endpoint"]);self.key=tk.StringVar()
        self.model=tk.StringVar(value=self.cfg.get("model",""))
        self.protocol=tk.StringVar(value=next(k for k,v in PROTOCOLS.items() if v==reasoning_protocol(self.cfg)))
        policy=self.cfg.get("reasoning",{})
        level=policy.get("default","medium");level=level if level in LEVELS else "medium"
        self.level=tk.StringVar(value=next(k for k,v in LEVEL_LABELS.items() if v==level))
        self.auto=tk.BooleanVar(value=policy.get("mode","auto")!="fixed")
        self.vision=tk.BooleanVar(value=self.cfg.get("vision",{}).get("enabled",False))
        self.proxy=tk.BooleanVar(value=self.cfg.get("trust_env",False))
        self.check_models=tk.BooleanVar(value=self.cfg.get("check_models",True))
        self.token=tk.StringVar(value=self.cfg.get("output_token_parameter","max_tokens"))
        try:has_key=bool(api_headers(self.cfg))
        except Exception:has_key=True
        local=urlsplit(self.cfg["endpoint"]).hostname in ("localhost","127.0.0.1","::1")
        self.no_key=tk.BooleanVar(value=local and not has_key)
        self.previous_endpoint=normalize_endpoint(self.cfg["endpoint"])
        self.show=tk.BooleanVar();self.advanced=tk.BooleanVar()
        self.status=tk.StringVar(value="保存后下一次生成生效；当前生成中的回复沿用原设置。")
        self.protocol_note=tk.StringVar()
        self.footer=ttk.Frame(self.root,padding=12);self.footer.pack(side="bottom",fill="x")
        self.save_button=ttk.Button(self.footer,text="保存设置",command=self.save);self.save_button.pack(side="right")
        ttk.Button(self.footer,text="关闭",command=self.close).pack(side="right",padx=8)
        ttk.Label(self.footer,textvariable=self.status,wraplength=620).pack(side="left")
        outer=ttk.Frame(self.root);outer.pack(fill="both",expand=True)
        self.canvas=tk.Canvas(outer,highlightthickness=0)
        scroll=ttk.Scrollbar(outer,orient="vertical",command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set);scroll.pack(side="right",fill="y");self.canvas.pack(side="left",fill="both",expand=True)
        body=ttk.Frame(self.canvas,padding=12);self.body=body
        window=self.canvas.create_window((0,0),window=body,anchor="nw")
        body.bind("<Configure>",lambda e:self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",lambda e:self.canvas.itemconfigure(window,width=e.width))
        ttk.Label(body,text="输入模型接口地址和Key，获取列表后选择模型。列表不代表已获全部模型调用权限。",wraplength=850).pack(anchor="w",pady=(0,10))
        network=ttk.LabelFrame(body,text="模型接口",padding=10);network.pack(fill="x")
        network.columnconfigure(1,weight=1)
        ttk.Label(network,text="API地址").grid(row=0,column=0,sticky="w",pady=5)
        self.address_entry=ttk.Entry(network,textvariable=self.endpoint);self.address_entry.grid(row=0,column=1,sticky="ew",padx=8)
        self.fetch_button=ttk.Button(network,text="获取模型列表",command=self.fetch);self.fetch_button.grid(row=0,column=2)
        ttk.Label(network,text="API Key").grid(row=1,column=0,sticky="w",pady=5)
        self.key_entry=ttk.Entry(network,textvariable=self.key,show="●");self.key_entry.grid(row=1,column=1,sticky="ew",padx=8)
        ttk.Checkbutton(network,text="显示输入",variable=self.show,command=lambda:self.key_entry.configure(show="" if self.show.get() else "●")).grid(row=1,column=2)
        self.no_key_button=ttk.Checkbutton(network,text="此接口无需Key（如本地模型）",variable=self.no_key,command=self.key_state)
        self.no_key_button.grid(row=2,column=1,sticky="w",padx=8,pady=4)
        ttk.Label(network,text="已有密钥时留空沿用；换接口地址请重新填Key。新Key用Windows账户加密保存，不写进config.json。",wraplength=810).grid(row=3,column=0,columnspan=3,sticky="w",pady=4)
        ttk.Label(network,text="模型").grid(row=4,column=0,sticky="w",pady=5)
        self.model_box=ttk.Combobox(network,textvariable=self.model,values=[self.model.get()] if self.model.get() else [])
        self.model_box.grid(row=4,column=1,sticky="ew",padx=8)
        ttk.Button(network,text="使用本地默认",command=self.local_defaults).grid(row=4,column=2)
        ttk.Checkbutton(network,text="原生识图（所选模型需支持图片输入）",variable=self.vision).grid(row=5,column=1,sticky="w",padx=8,pady=5)
        self.proxy_button=ttk.Checkbutton(network,text="使用环境代理",variable=self.proxy);self.proxy_button.grid(row=5,column=2)
        ttk.Checkbutton(network,text="启动时检查模型列表（接口不提供列表时可关闭，模型ID需手填）",variable=self.check_models).grid(row=6,column=1,columnspan=2,sticky="w",padx=8,pady=4)
        thinking=ttk.LabelFrame(body,text="思考程度",padding=10);thinking.pack(fill="x",pady=10);thinking.columnconfigure(1,weight=1)
        ttk.Label(thinking,text="参数格式").grid(row=0,column=0,sticky="w",pady=4)
        self.protocol_box=ttk.Combobox(thinking,textvariable=self.protocol,values=list(PROTOCOLS),state="readonly",width=40)
        self.protocol_box.grid(row=0,column=1,sticky="w",padx=8);self.protocol_box.bind("<<ComboboxSelected>>",self.protocol_changed)
        ttk.Label(thinking,text="默认程度").grid(row=1,column=0,sticky="w",pady=4)
        ttk.Combobox(thinking,textvariable=self.level,values=list(LEVEL_LABELS),state="readonly",width=20).grid(row=1,column=1,sticky="w",padx=8)
        ttk.Checkbutton(thinking,text="复杂问题自动提高到高（取消后固定使用所选档位）",variable=self.auto).grid(row=2,column=1,sticky="w",padx=8,pady=4)
        ttk.Label(thinking,textvariable=self.protocol_note,wraplength=820).grid(row=3,column=0,columnspan=2,sticky="w",pady=6)
        ttk.Checkbutton(body,text="显示高级参数：token预算、生成上限与超时",variable=self.advanced,command=self.toggle_advanced).pack(anchor="w")
        self.advanced_frame=ttk.LabelFrame(body,text="高级参数",padding=10);self.limits={}
        for col,label in enumerate(["档位","思考token预算","总生成token上限","超时（秒）"]):ttk.Label(self.advanced_frame,text=label).grid(row=0,column=col,padx=8)
        for index,effort in enumerate(LEVELS,1):
            values=dict(DEFAULT_LIMITS[effort]);values.update(policy.get(effort,{}));self.limits[effort]={}
            ttk.Label(self.advanced_frame,text=next(k for k,v in LEVEL_LABELS.items() if v==effort)).grid(row=index,column=0,padx=8,pady=3)
            for col,name in enumerate(["budget","max_tokens","timeout_seconds"],1):
                variable=tk.StringVar(value=str(0 if effort=="none" and name=="budget" else values[name]))
                self.limits[effort][name]=variable
                ttk.Entry(self.advanced_frame,textvariable=variable,width=18,state="disabled" if effort=="none" and name=="budget" else "normal").grid(row=index,column=col,padx=8,pady=3)
        ttk.Label(self.advanced_frame,text="预算仅Strata模式发送；Strata总上限含思考和正文，API以服务定义为准。过大可能超出上下文。",wraplength=800).grid(row=5,column=0,columnspan=4,sticky="w",pady=6)
        ttk.Label(self.advanced_frame,text="生成上限字段").grid(row=6,column=0,sticky="w")
        ttk.Combobox(self.advanced_frame,textvariable=self.token,values=["max_tokens","max_completion_tokens"],state="readonly",width=28).grid(row=6,column=1,columnspan=2,sticky="w",padx=8)
        self.key_state();self.protocol_changed()
        self.endpoint.trace_add("write",self.address_changed)
        self.root.protocol("WM_DELETE_WINDOW",self.close);self.after_id=self.root.after(100,self.pump)
    def address_changed(self,*args):
        try:endpoint=normalize_endpoint(self.endpoint.get())
        except ValueError:return
        if self.previous_endpoint!=endpoint:
            self.model.set("");self.model_box["values"]=[];self.key.set("")
            self.no_key.set(False);self.key_state()
            self.protocol.set(next(k for k,v in PROTOCOLS.items() if v=="off"))
            self.protocol_changed()
            self.status.set("接口地址已改变，请填写该服务的Key并重新获取模型；新接口默认兼容参数。")
        self.previous_endpoint=endpoint
    def key_state(self):
        self.key_entry.configure(state="disabled" if self.no_key.get() or self.busy else "normal")
    def protocol_changed(self,event=None):
        value=PROTOCOLS[self.protocol.get()]
        notes={
         "off":"兼容模式不向服务端发送思考参数，档位不会控制模型实际思考；生成上限与超时仍生效。",
         "effort":"只发送reasoning_effort，不发送Strata预算。服务商和模型需支持对应档位；部分接口不接受none。",
         "strata":"用于本地Strata：none关闭思考，low/medium/high配合各自token预算。"}
        self.protocol_note.set(notes[value])
    def toggle_advanced(self):
        if self.advanced.get():self.advanced_frame.pack(fill="x",pady=8)
        else:self.advanced_frame.pack_forget()
    def local_defaults(self):
        if self.busy:return
        self.endpoint.set("http://127.0.0.1:8095/v1/chat/completions")
        self.model.set("deepseek-v4.1-flash");self.key.set("");self.no_key.set(True);self.key_state()
        self.protocol.set(next(k for k,v in PROTOCOLS.items() if v=="strata"));self.protocol_changed()
        self.level.set("中");self.auto.set(True);self.vision.set(True)
        self.status.set("已填本地默认值；点击保存后生效。")
    def set_busy(self,value):
        self.busy=value
        for w in [self.address_entry,self.no_key_button,self.proxy_button,self.fetch_button,self.save_button,self.model_box]:
            w.configure(state="disabled" if value else "normal")
        self.key_state()
    def fetch(self):
        if self.busy:return
        try:
            endpoint=normalize_endpoint(self.endpoint.get())
            headers=preview_headers(self.cfg,endpoint,self.key.get(),self.no_key.get())
        except Exception as exc:messagebox.showerror("填写有误",str(exc),parent=self.root);return
        self.set_busy(True);self.status.set("正在获取模型列表……")
        proxy=self.proxy.get()
        def work():
            try:self.queue.put((True,fetch_models(endpoint,headers,proxy)))
            except Exception as exc:self.queue.put((False,str(exc)))
        threading.Thread(target=work,daemon=True).start()
    def pump(self):
        if self.closed:return
        try:
            while True:
                ok,value=self.queue.get_nowait();self.set_busy(False)
                if ok:
                    self.model_box["values"]=value
                    if self.model.get() not in value:self.model.set(value[0] if len(value)==1 else "")
                    self.status.set("已获取%d个模型，选择后保存；调用权限仍由服务商决定。"%len(value))
                else:self.status.set(value);messagebox.showerror("获取失败",value,parent=self.root)
        except queue.Empty:pass
        self.after_id=self.root.after(100,self.pump)
    def values(self):
        return dict(endpoint=self.endpoint.get(),model=self.model.get(),protocol=PROTOCOLS[self.protocol.get()],
                    level=LEVEL_LABELS[self.level.get()],auto=self.auto.get(),vision=self.vision.get(),trust_env=self.proxy.get(),check_models=self.check_models.get(),
                    output_token_parameter=self.token.get(),
                    limits={effort:{name:variable.get() for name,variable in fields.items()} for effort,fields in self.limits.items()})
    def save(self):
        if self.busy:return
        try:
            save_settings(self.path,self.values(),self.key.get(),self.no_key.get(),self.original)
            self.original=self.path.read_bytes();self.cfg=load_config(self.path);self.key.set("")
            self.status.set("已保存；关闭窗口后恢复原监听（若原先在运行），新设置下一次生成生效。")
        except Exception as exc:messagebox.showerror("未保存",str(exc),parent=self.root);self.status.set("未保存，请检查填写内容。")
    def close(self):
        if self.on_close:
            self.status.set("正在恢复原来的监听状态……");self.root.update_idletasks()
            try:self.on_close()
            except Exception as exc:messagebox.showerror("监听未恢复",str(exc),parent=self.root)
        self.closed=True
        if self.after_id:self.root.after_cancel(self.after_id)
        self.root.destroy()
    def run(self):self.root.mainloop()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--config",type=Path);args=p.parse_args()
    from settings_listener import ListenerControl
    path=Path(args.config or ROOT/"config.json")
    controller=ListenerControl(path.resolve().parent)
    try:
        controller.pause()
        app=ModelSettings(path,on_close=controller.resume)
        if controller.was_running:app.status.set("原监听已暂停，关闭窗口后恢复；本地模型继续运行。")
        app.run()
    except Exception as exc:
        try:controller.resume()
        except Exception:pass
        root=tk.Tk();root.withdraw();messagebox.showerror("无法打开模型设置",str(exc));root.destroy();return 1
    return 0
if __name__=="__main__":raise SystemExit(main())
