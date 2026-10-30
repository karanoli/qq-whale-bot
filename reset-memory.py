import json,shutil,subprocess,sys,datetime,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OWNER='QQWhaleBot-Reset'
KEEP=3
NAMES=['conversations','state.json','last-batch.json','last-transcript.txt','last-model-reply.json','bot-log.jsonl','bot-log.jsonl.1','bot-log.jsonl.2','bot-log.jsonl.3','bot-status.json']
def reset_files(root):
    root=Path(root).resolve()
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup=root/'memory-backups'/stamp;backup.mkdir(parents=True,exist_ok=False)
    moved=[]
    try:
        for name in NAMES:
            src=root/name
            if src.exists():shutil.move(str(src),str(backup/name));moved.append(name)
        (backup/'reset-manifest.json').write_text(json.dumps(dict(owner=OWNER,archived=moved),ensure_ascii=False),encoding='utf-8')
    except Exception:
        for name in reversed(moved):shutil.move(str(backup/name),str(root/name))
        raise
    managed=[]
    for folder in backup.parent.iterdir():
        if folder.is_symlink() or not folder.is_dir() or not re.fullmatch(r'\d{8}-\d{6}-\d{6}',folder.name):continue
        try:manifest=json.loads((folder/'reset-manifest.json').read_text(encoding='utf-8'))
        except Exception:continue
        if manifest.get('owner')==OWNER:managed.append(folder)
    removed=[];warnings=[]
    for folder in sorted(managed,key=lambda p:p.name,reverse=True)[KEEP:]:
        try:shutil.rmtree(folder);removed.append(folder.name)
        except Exception as e:warnings.append(str(e))
    report=dict(time=datetime.datetime.now().isoformat(timespec='seconds'),backup=str(backup),archived=moved,retained_backups=KEEP,removed_old_backups=removed,warnings=warnings,targets_preserved=True,personality_preserved=True,bot_stopped=True)
    (root/'reset-last.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report

def main():
    subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'stop.ps1')],check=True,timeout=25)
    report=reset_files(ROOT)
    print('小鲸记忆已重置，机器人保持停止。')
    print('监听名单、人格、模型设置均已保留。')
    print('备份位置：'+report['backup'])
    print('只保留最近3份重置备份，较旧的自动清理。')
    print('准备好 QQ 后，运行 start.cmd。启动会将可读旧消息作为已读基线。')
if __name__=='__main__':
    try:main()
    except Exception as e:print('重置未完成：'+str(e));sys.exit(1)
