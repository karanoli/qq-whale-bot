from pathlib import Path
import os
MAX_LOG_BYTES=2*1024*1024
LOG_ARCHIVES=3
def rotate_log(path):
    path=Path(path)
    if not path.exists() or path.stat().st_size<MAX_LOG_BYTES:return
    oldest=Path(str(path)+'.'+str(LOG_ARCHIVES))
    if oldest.exists():oldest.unlink()
    for i in range(LOG_ARCHIVES-1,0,-1):
        src=Path(str(path)+'.'+str(i))
        if src.exists():os.replace(src,Path(str(path)+'.'+str(i+1)))
    os.replace(path,Path(str(path)+'.1'))
