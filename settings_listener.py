"""Pause only this checkout's scheduled QQ listener while editing settings."""
import json
import os
from pathlib import Path
import subprocess
class ListenerControl:
    def __init__(self,root):
        self.root=Path(root).resolve();self.was_running=False;self.resume_attempted=False
    def pause(self):
        if os.name!="nt":return
        command="Get-ScheduledTask -ErrorAction Stop | Where-Object {$_.TaskName -in @('QQWhaleBot','AIchat-Visual-Bot')} | Select TaskName,State,@{n='Arguments';e={$_.Actions.Arguments}} | ConvertTo-Json -Compress"
        p=subprocess.run(["powershell.exe","-NoProfile","-Command",command],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=20)
        if p.returncode:raise RuntimeError("无法查询监听任务；请先手动停止机器人")
        tasks=json.loads(p.stdout) if p.stdout.strip() else []
        if isinstance(tasks,dict):tasks=[tasks]
        expected=(self.root/"bot.py").resolve()
        def own(arguments):
            if not isinstance(arguments,str):return False
            value=arguments.strip()
            if value.endswith(" --run"):value=value[:-6].rstrip()
            if value.startswith('"') and value.endswith('"'):value=value[1:-1]
            try:
                path=Path(value)
                return path.is_absolute() and path.resolve()==expected
            except (OSError,ValueError):return False
        owned=[t for t in tasks if own(t.get("Arguments"))]
        self.was_running=any(t["State"]==4 or t["State"]=="Running" for t in owned)
        if self.was_running:
            stop=self.root/"stop.ps1"
            if not stop.exists():raise RuntimeError("未找到当前项目的停止入口")
            result=subprocess.run(["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",str(stop)],
                                  capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=30)
            if result.returncode:raise RuntimeError("未能暂停当前监听，未打开设置")
    def resume(self):
        if not self.was_running or self.resume_attempted:return
        self.resume_attempted=True
        p=subprocess.run(["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",str(self.root/"start.ps1")],
                         capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=240)
        if p.returncode:raise RuntimeError("设置已保存，但监听恢复失败，请检查模型接口并使用start.cmd重新启动")
