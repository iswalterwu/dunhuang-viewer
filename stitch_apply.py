# -*- coding: utf-8 -*-
"""处理手动拼接输出队列：把 cache/stitch_out/*.tif 搬到卷目录，并加入图块重建队列。"""
import glob, hashlib, base64, json, os, shutil, time

OUT = '/srv/example/cache/stitch_out'
DATA = '/srv/example/data'
CACHE = '/srv/example/cache'
STATE = os.path.join(CACHE, 'pyramid_build_state.json')
LOG = os.path.join(CACHE, 'stitch_apply.log')

def log(msg):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write('[%s] %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg))

for side in sorted(glob.glob(os.path.join(OUT, '*.json'))):
    try:
        info = json.load(open(side, encoding='utf-8'))
        rel = info['target']
        src = os.path.join(OUT, info.get('source_name') or (os.path.splitext(os.path.basename(side))[0] + '.tif'))
        if not os.path.exists(src):
            log('源文件不存在，清理: %s' % side)
            try: os.remove(side)
            except OSError: pass
            continue
        target = os.path.join(DATA, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        tmp = target + '.stitchtmp'
        shutil.copy2(src, tmp)
        os.replace(tmp, target)
        fid = base64.urlsafe_b64encode(rel.encode()).decode().rstrip('=')
        h = hashlib.sha1(fid.encode()).hexdigest()[:16]
        shutil.rmtree(os.path.join(CACHE, 'pyramids', h), ignore_errors=True)
        try: os.remove(os.path.join(CACHE, 'thumbs', h + '.jpg'))
        except OSError: pass
        try:
            st = json.load(open(STATE, encoding='utf-8'))
        except Exception:
            st = {'done': {}, 'failed': {}, 'attempts': {}, 'deferred': {}}
        st.setdefault('deferred', {})[rel] = {'ts': int(time.time())}
        tmp_state = STATE + '.tmp'
        json.dump(st, open(tmp_state, 'w', encoding='utf-8'), ensure_ascii=False)
        os.replace(tmp_state, STATE)
        os.remove(src)
        os.remove(side)
        log('已应用: %s (%.1f MB)' % (rel, os.path.getsize(target) / 1e6))
    except Exception as exc:
        log('应用失败: %s | %s' % (side, exc))