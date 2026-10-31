import tkinter as tk
from tkinter import ttk,messagebox
import json,re,threading,queue,subprocess,os,traceback,sys
from desktop import ROOT
from transport import Transport
from memory import targets,key,atomic,Memory
from runtime import load_config
CFG=load_config()
POWERSHELL=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass']
class Manager:
    def __init__(self):
        self.root=tk.Tk();self.root.title('小鲸 · 监听管理');self.root.geometry('900x560');self.queue=queue.Queue();self.ready=False;self.busy=False;self.was_running=False;self.pending_original=None
        self.kind=tk.StringVar(value='group');self.number=tk.StringVar();self.name=tk.StringVar();self.status=tk.StringVar(value='正在暂停监听，准备编辑……')
        ttk.Label(self.root,text='输入群号或 QQ 号，核对会话后加入监听。每个会话的记忆独立保存。',padding=12).pack(anchor='w')
        self.tree=ttk.Treeview(self.root,columns=('kind','number','name','enabled'),show='headings',height=9,selectmode='browse')
        for c,title,width in [('kind','类型',65),('number','号码',145),('name','名称',420),('enabled','监听',80)]:self.tree.heading(c,text=title);self.tree.column(c,width=width)
        self.tree.pack(fill='both',expand=True,padx=12);self.tree.bind('<<TreeviewSelect>>',self.selected)
        form=ttk.Frame(self.root,padding=12);form.pack(fill='x')
        ttk.Radiobutton(form,text='群聊',value='group',variable=self.kind).grid(row=0,column=0,sticky='w');ttk.Radiobutton(form,text='个人',value='private',variable=self.kind).grid(row=0,column=1,sticky='w')
        ttk.Label(form,text='群号 / QQ号').grid(row=1,column=0,sticky='w',pady=8);ttk.Entry(form,textvariable=self.number,width=24).grid(row=1,column=1,sticky='w')
        ttk.Label(form,text='完整群名 / 昵称').grid(row=1,column=2,padx=(15,5));ttk.Entry(form,textvariable=self.name,width=33).grid(row=1,column=3,sticky='w')
        ttk.Label(form,text='改名：选中对象后修改名称，点击修改。改号码会按新对象核验，原记忆保留。').grid(row=2,column=0,columnspan=4,sticky='w')
        buttons=ttk.Frame(self.root,padding=(12,0));buttons.pack(fill='x')
        self.add=ttk.Button(buttons,text='新增侦测',command=self.add_target);self.add.pack(side='left')
        self.edit=ttk.Button(buttons,text='修改选中对象',command=self.edit_target);self.edit.pack(side='left',padx=8)
        self.remove=ttk.Button(buttons,text='删除选中对象',command=self.delete_target);self.remove.pack(side='left')
        self.toggle=ttk.Button(buttons,text='启用 / 停用选中会话',command=self.toggle_target);self.toggle.pack(side='left',padx=8)
        ttk.Button(buttons,text='查看选中会话的记忆文件',command=self.show_memory).pack(side='left')
        ttk.Label(self.root,textvariable=self.status,padding=12,wraplength=860).pack(fill='x')
        bottom=ttk.Frame(self.root,padding=12);bottom.pack(fill='x')
        ttk.Button(bottom,text='模型与思考设置',command=lambda:subprocess.Popen([sys.executable,str(ROOT/'model_settings.py')])).pack(side='left',padx=(0,10))
        self.go=ttk.Button(bottom,text='保存并开始监听',command=lambda:self.close(True));self.go.pack(side='right')
        ttk.Button(bottom,text='保持停止并关闭',command=lambda:self.close(False)).pack(side='right',padx=8)
        ttk.Label(bottom,text='打开管理窗口时暂停机器人，避免鼠标键盘冲突。').pack(side='left')
        self.root.protocol('WM_DELETE_WINDOW',lambda:self.close(self.was_running));self.refresh();self.set_busy(True)
        threading.Thread(target=self.prepare,daemon=True).start();self.root.after(150,self.pump)
    def set_busy(self,value):
        self.busy=value
        for button in [self.add,self.edit,self.remove,self.toggle,self.go]:button.configure(state='disabled' if value else 'normal')
    def prepare(self):
        try:
            r=subprocess.run(POWERSHELL+['-Command',"(Get-ScheduledTask QQWhaleBot -ErrorAction SilentlyContinue).State"],capture_output=True,timeout=15)
            self.was_running=b'Running' in r.stdout
            subprocess.run(POWERSHELL+['-File',str(ROOT/'stop.ps1')],capture_output=True,timeout=20,check=True)
            (ROOT/'STOP').unlink(missing_ok=True);self.queue.put(('ready',None))
        except Exception as e:self.queue.put(('prepare_error',str(e)))
    def refresh(self):
        self.data=targets();selected=self.tree.selection();self.tree.delete(*self.tree.get_children())
        for t in self.data:self.tree.insert('',tk.END,iid=key(t),values=('群聊' if t['kind']=='group' else '个人',t['id'],t['name'],'启用' if t.get('enabled',True) else '停用'))
        if selected and self.tree.exists(selected[0]):self.tree.selection_set(selected[0])
    def selected(self,event=None):
        ids=self.tree.selection()
        if ids:
            t=next(x for x in self.data if key(x)==ids[0]);self.kind.set(t['kind']);self.number.set(t['id']);self.name.set(t['name'])
    def chosen(self):
        ids=self.tree.selection()
        return next((t for t in self.data if ids and key(t)==ids[0]),None)
    def read_form(self):
        number=self.number.get().strip();name=self.name.get().strip();kind=self.kind.get()
        if kind not in ('group','private') or not re.fullmatch(r'\d{5,12}',number):raise ValueError('请输入 5 至 12 位纯数字群号或 QQ 号。')
        if not name or len(name)>70:raise ValueError('请填写 QQ 中当前显示的完整群名或昵称，最多70字。')
        return dict(kind=kind,id=number,name=name)
    def add_target(self):
        if self.busy:return
        try:target=self.read_form()
        except ValueError as e:messagebox.showerror('输入有误',str(e));return
        if any(key(t)==key(target) for t in self.data):messagebox.showinfo('已在列表中','这个号码已经加入，请选中后点击“修改选中对象”。');return
        self.pending_original=None;self.validate()
    def edit_target(self):
        if self.busy:return
        original=self.chosen()
        if original is None:messagebox.showinfo('先选择对象','请先点击列表中的群聊或个人。');return
        try:target=self.read_form()
        except ValueError as e:messagebox.showerror('输入有误',str(e));return
        if key(target)==key(original):
            original['name']=target['name'];self.persist();self.status.set('名称已修改，启用状态和聊天记忆保留。');return
        if any(key(t)==key(target) for t in self.data):messagebox.showerror('对象重复','新号码已在列表中，请直接修改那一行。');return
        if not messagebox.askyesno('更换侦测对象','类型或号码已经改变。核验成功后替换选中对象，新旧对象使用各自的记忆；原记忆保留。继续？'):return
        self.pending_original=key(original);self.validate()
    def delete_target(self):
        if self.busy:return
        original=self.chosen()
        if original is None:messagebox.showinfo('先选择对象','请先点击列表中的群聊或个人。');return
        label=('群聊' if original['kind']=='group' else '个人')+'：'+original['name']+'（'+original['id']+'）'
        if not messagebox.askyesno('删除侦测对象','停止侦测 '+label+'？'+chr(10)+'历史记忆保留，重新添加同一号码时可继续使用。'):return
        self.data=[t for t in self.data if key(t)!=key(original)];self.persist()
        self.number.set('');self.name.set('');self.status.set('已删除侦测对象，历史记忆保留。')
    def apply_verified(self,target):
        old=self.pending_original
        matches=[t for t in self.data if key(t)==key(target) and key(t)!=old]
        if matches:raise ValueError('该号码已在列表中；未修改配置。')
        index=next((i for i,t in enumerate(self.data) if key(t)==old),len(self.data))
        existing=next((t for t in self.data if key(t)==old),None)
        if old and existing is None:raise ValueError('原对象已发生变化；请重新选择。')
        target=dict(existing or {},**target)
        if existing:target['enabled']=existing.get('enabled',True)
        remaining=[t for t in self.data if key(t)!=old];remaining.insert(index,target);self.data=remaining
        self.pending_original=None;self.persist()
    def validate(self):
        if self.busy:return
        number=self.number.get().strip();name=self.name.get().strip();kind=self.kind.get()
        if not re.fullmatch(r'\d{5,12}',number):messagebox.showerror('号码有误','请输入 5 至 12 位纯数字号码。');return
        if len(name)>70:messagebox.showerror('名称过长','请填写 QQ 显示的完整名称。');return
        target=dict(kind=kind,id=number,name=name,enabled=True)
        self.set_busy(True);self.status.set('正在 QQ 中核对，请暂时不要操作鼠标键盘……');self.root.iconify()
        def work():
            try:
                t=Transport(dict(CFG,target=target));rows=t.collect();self.queue.put(('verified',(target,rows)))
            except Exception:self.queue.put(('verify_error',traceback.format_exc()))
        threading.Thread(target=work,daemon=True).start()
    def persist(self):
        path=ROOT/'targets.json'
        if path.exists():atomic(ROOT/'targets-before-change.json',json.loads(path.read_text(encoding='utf-8')))
        atomic(path,dict(version=2,targets=self.data));self.refresh()
    def toggle_target(self):
        if self.busy:return
        ids=self.tree.selection()
        if not ids:return
        t=next(x for x in self.data if key(x)==ids[0]);t['enabled']=not t.get('enabled',True);self.persist();self.status.set('已保存；关闭管理窗口并开始监听后生效。记忆文件保持独立保留。')
    def show_memory(self):
        ids=self.tree.selection()
        if not ids:return
        path=ROOT/'conversations'/ids[0]/'memory.json'
        if not path.exists():messagebox.showinfo('尚无记忆','该会话尚未建立记忆。');return
        subprocess.Popen(['notepad.exe',str(path)])
    def pump(self):
        try:
            while True:
                event,value=self.queue.get_nowait()
                if event=='ready':self.ready=True;self.set_busy(False);self.status.set('监听已暂停，可以输入并核验新会话。关闭窗口将恢复原来的运行状态。')
                elif event=='verified':
                    self.root.deiconify();self.root.lift();target,rows=value
                    ok=messagebox.askyesno('确认侦测对象',('群聊' if target['kind']=='group' else '个人')+'：'+target['name']+'\n号码：'+target['id']+'\n\nQQ 已核验。确认加入监听并使用独立记忆？')
                    if ok:
                        memory=Memory(target)
                        if not memory.data['initialized']:
                            memory.data['bot_names']=CFG.get('self_names',[]);memory.merge(rows,baseline=True)
                        self.apply_verified(target);self.status.set('已保存：'+target['name']+'。点击“保存并开始监听”即可。')
                    else:self.status.set('已取消添加。')
                    self.set_busy(False)
                elif event=='verify_error':
                    self.root.deiconify();self.root.lift();(ROOT/'manager-error.log').write_text(value,encoding='utf-8');messagebox.showerror('未完成核验','未能确认目标。请检查号码、完整群名和 QQ 窗口。详细原因见 manager-error.log。');self.status.set('尚未添加；修改输入后可以重试。');self.set_busy(False)
                elif event=='prepare_error':
                    self.ready=True;self.busy=False
                    self.status.set('暂停监听失败，请先运行 stop.cmd，关闭本窗口后重试。');messagebox.showerror('准备失败',value)
        except queue.Empty:pass
        self.root.after(150,self.pump)
    def close(self,resume):
        if not self.ready or self.busy:messagebox.showinfo('稍等','正在准备或核验，请完成后再关闭。');return
        if not resume:(ROOT/'STOP').write_text('stop',encoding='ascii')
        self.root.destroy()
        if resume:subprocess.Popen(POWERSHELL+['-File',str(ROOT/'start.ps1')],creationflags=subprocess.CREATE_NEW_CONSOLE)
    def run(self):self.root.mainloop()
if __name__=='__main__':Manager().run()
