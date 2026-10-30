from desktop import check_stop

class Vision:
    def __init__(self,cfg):self.cfg=cfg.get('vision',{})
    def enrich(self,memory,transport=None):
        if not self.cfg.get('enabled',True):return
        if self.cfg.get('mode')!='native':raise RuntimeError('Native mode expected')
        from desktop import Stopped
        from native_vision import fresh_rows,valid_image
        rows=[r for r in fresh_rows(memory) if r.get('image_count') or r.get('image_refs')]
        for row in rows[-1:]:
            errors=[];paths=[]
            for value in row.get('images',[])[:1]:
                try:paths.append(str(valid_image(value,memory)))
                except (ValueError,OSError):pass
            if not paths and transport is not None and row.get('image_refs'):
                from uia_image import capture
                for index,reference in enumerate(row['image_refs'][:1]):
                    try:paths.append(capture(transport,row,reference,index,memory.directory))
                    except Stopped:raise
                    except Exception as e:errors.append(str(e))
            row['images']=paths;row['vision']=[];row['vision_mode']='native'
            if errors:row['vision_error']='; '.join(errors)[-1000:]
            else:row.pop('vision_error',None)
        memory.save()
