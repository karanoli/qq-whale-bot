import re

def choose(memory,cfg):
    policy=cfg.get('reasoning',{});pending=set(memory.data.get('pending',[]))
    rows=[r for r in memory.data.get('messages',[]) if r['id'] in pending and not memory.is_self(r)]
    if not rows:rows=[r for r in memory.data.get('messages',[]) if not memory.is_self(r)][-1:]
    rows=rows[-4:]
    text=chr(10).join(re.sub(r'<img[^>]*>','',r['body'],flags=re.I) for r in rows)[-6000:]
    observed=' '.join(' '.join(r.get('vision',[])) for r in rows)
    effort=policy.get('default','medium');reason='default'
    low_request=re.search(r'(不用|不要|别|关闭).{0,8}(高|深度|高档)(推理|思考)',text)
    medium_request=re.search(r'(中档|中等|中度|中级)(推理|思考)',text)
    high_request=re.search(r'高(档|强度)?(推理|思考)|深度(推理|思考)|认真(推理|分析)|深入(推理|分析)',text)
    domain=re.search(r'数学|函数|方程|整数|整除|数列|几何|概率|积分|导数|极限|矩阵|算法|复杂度|动态规划|数据结构|洛谷|ACM|代码|程序|编译|报错|debug|漏洞|死锁',text,re.I) or 'C++' in text
    action=re.search(r'证明|推导|求解|求证|计算|分析|实现|检查|修复|帮.{0,8}(解|算|证|改)|怎么(做|解|求|写|改)|如何(做|解|求|写|改)',text)
    hard=re.search(r'证明|推导|最优|复杂度|动态规划|死锁|漏洞|内存越界|溢出',text)
    code=(chr(96)*3 in text or '#include' in text or 'Traceback (most recent call last)' in text or bool(re.search(r'(class|def) [A-Za-z_]+',text))) and len(text)>160
    visual_task=bool(re.search(r'数学|方程|公式|几何|程序|代码|题目',observed)) and bool(action)
    if low_request or medium_request:effort='medium';reason='explicit_medium'
    elif high_request:effort='high';reason='explicit_high'
    elif code or visual_task or (domain and action and (hard or len(text)>220)):effort='high';reason='complex_task'
    if effort not in ('medium','high'):effort='medium'
    defaults={'medium':dict(budget=384,max_tokens=1152,timeout_seconds=300),'high':dict(budget=1536,max_tokens=2304,timeout_seconds=600)}
    limits=dict(defaults[effort]);limits.update(policy.get(effort,{}))
    return dict(effort=effort,reason=reason,reasoning_budget_tokens=int(limits['budget']),max_tokens=int(limits['max_tokens']),timeout_seconds=int(limits['timeout_seconds']))
