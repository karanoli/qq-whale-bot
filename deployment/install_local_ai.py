"""Pinned Windows DeepSeek native-vision installer. No QQ interaction."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile
import time
import zipfile

REPO = Path(__file__).resolve().parents[1]
def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))
def atomic(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)
def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""): h.update(block)
    return h.hexdigest()
def checked_root(path, repo=REPO):
    path, repo = Path(path).resolve(), Path(repo).resolve()
    if path == Path(path.anchor) or path == repo:
        raise ValueError("AiRoot 不能是磁盘根目录或仓库根目录")
    if path.is_relative_to(repo) and not path.is_relative_to(repo / ".local-ai"):
        raise ValueError("模型放在仓库外或 .local-ai 内，避免混入源码")
    return path
def effective_url(url, endpoint):
    if endpoint and url.startswith("https://huggingface.co/"):
        if not endpoint.startswith("https://") or "?" in endpoint or "#" in endpoint:
            raise ValueError("HF endpoint 必须是 HTTPS 根地址")
        return endpoint.rstrip("/") + url[len("https://huggingface.co"):]
    return url
def download(asset, directory, receipts, endpoint=None, session=None):
    import requests
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    name = asset["filename"]
    if Path(name).name != name: raise ValueError("Unsafe asset filename")
    dest = directory / name
    expected = int(asset["size"]); digest = asset["sha256"]
    key = str(dest.resolve())
    def verified():
        info = dest.stat()
        receipts[key] = dict(size=info.st_size, mtime_ns=info.st_mtime_ns, sha256=digest)
        return dest
    if dest.exists():
        info = dest.stat(); old = receipts.get(key, {})
        if info.st_size == expected and old == dict(size=info.st_size, mtime_ns=info.st_mtime_ns, sha256=digest):
            return dest
        if info.st_size == expected and sha256(dest) == digest: return verified()
        raise ValueError("现有文件校验不符，未覆盖：" + str(dest))
    partial = dest.with_name(name + ".part")
    if partial.exists() and partial.stat().st_size > expected:
        raise ValueError("续传文件超出锁定大小：" + str(partial))
    session = session or requests.Session()
    url = effective_url(asset["url"], endpoint)
    for attempt in range(6):
        try:
            count = partial.stat().st_size if partial.exists() else 0
            if count < expected:
                response = session.get(url, headers={"Range": "bytes=%d-" % count} if count else {},
                                       stream=True, timeout=(25, 90))
                response.raise_for_status()
                if count and response.status_code == 206:
                    actual = response.headers.get("Content-Range", "")
                    if not actual.startswith("bytes %d-" % count):
                        raise ValueError("续传响应起点错误，未追加")
                elif response.status_code == 200:
                    count = 0
                elif count:
                    raise ValueError("续传响应状态错误")
                last = 0
                with contextlib.closing(response), partial.open("ab" if count else "wb") as f:
                    for block in response.iter_content(1024 * 1024):
                        if not block: continue
                        if count + len(block) > expected: raise ValueError("下载响应大于锁定文件")
                        f.write(block); count += len(block)
                        if time.monotonic() - last > 8:
                            print("%s: %.1f / %.1f GB" % (name, count / 1e9, expected / 1e9), flush=True)
                            last = time.monotonic()
            if partial.stat().st_size != expected: raise IOError("下载未完成")
            if sha256(partial) != digest: raise ValueError("SHA256 不符，未安装：" + str(partial))
            os.replace(partial, dest)
            return verified()
        except ValueError:
            raise
        except (requests.RequestException, OSError) as exc:
            if attempt == 5: raise RuntimeError("下载中断；重跑同一命令续传：" + name) from exc
            print("连接中断，保留分片并重试：" + name, flush=True)
            time.sleep(min(5 * (attempt + 1), 20))
    raise AssertionError("unreachable")
def extract_checked(archive, destination):
    destination = Path(destination); destination.mkdir(parents=True, exist_ok=True)
    def valid(name):
        result = (destination / name).resolve()
        if not result.is_relative_to(destination.resolve()): raise ValueError("Unsafe archive path")
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist():
                valid(item.filename)
                if stat.S_ISLNK(item.external_attr >> 16): raise ValueError("Archive symlink rejected")
            z.extractall(destination)
    else:
        with tarfile.open(archive) as t:
            for item in t.getmembers():
                valid(item.name)
                if not (item.isfile() or item.isdir()): raise ValueError("Archive links/devices rejected")
            t.extractall(destination)
def install_archive(archive, destination, digest):
    destination = Path(destination)
    marker = destination / ".qqwhale-installed.json"
    if marker.exists():
        if read_json(marker).get("sha256") != digest: raise ValueError("安装目录属于其他版本")
        return destination
    if destination.exists() and any(destination.iterdir()): raise ValueError("目录非空且非本程序安装，未覆盖：" + str(destination))
    stage = destination.with_name(destination.name + ".extracting")
    if stage.exists(): shutil.rmtree(stage)
    extract_checked(archive, stage); atomic(stage / marker.name, dict(sha256=digest))
    if destination.exists(): destination.rmdir()
    stage.rename(destination); return destination
@contextlib.contextmanager
def install_lock(root):
    p = Path(root) / "install.lock"; p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a+b") as f:
        f.seek(0)
        if not f.read(1): f.write(b"0"); f.flush()
        f.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try: yield
        finally:
            f.seek(0)
            if os.name == "nt": msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else: fcntl.flock(f.fileno(), fcntl.LOCK_UN)
def reuse_candidates(root):
    if root is None: return {}
    root = Path(root).resolve()
    if root == Path(root.anchor): raise ValueError("ReuseModels 必须指向模型目录，不能扫描整盘")
    if not root.is_dir(): raise ValueError("ReuseModels目录不存在")
    result = {}
    for p in root.rglob("*.gguf"): result.setdefault(p.name, []).append(p)
    return result
def pack_arguments(source, model_root, pack, files):
    backbone = model_root / "backbone"; shared = model_root / "shared"
    names = [a["filename"] for a in files if a["group"] == "backbone"]
    meta = next(a["filename"] for a in files if "UD-Q8_K_XL-" in a["filename"])
    dspark = next(a["filename"] for a in files if a["filename"].startswith("dspark-"))
    vision = next(a["filename"] for a in files if a["filename"].startswith("mmproj-"))
    return [str(source / "tools/dsv41/pack_gguf.py"), "--model", str(backbone),
            "--out", str(pack), "--config-json", str(REPO / "deployment/deepseek-config.json"),
            "--engram", str(model_root / "engram"), "--engram-meta", str(shared / meta),
            "--dspark-gguf", str(shared / dspark), "--dspark-noise-token", "128799",
            "--dspark-markov-rank", "256", "--mmproj", str(shared / vision),
            "--shards"] + names
def run(argv, **kwargs):
    print("执行：" + str(argv[0]), flush=True)
    subprocess.run([str(x) for x in argv], check=True, **kwargs)
def remaining_weight_bytes(root,files,reuse):
    need=0
    for a in files:
        dest=Path(root)/"models"/a["group"]/a["filename"]
        if dest.exists() or any(p.stat().st_size==a["size"] for p in reuse.get(a["filename"],[])):continue
        partial=dest.with_name(dest.name+".part")
        have=min(partial.stat().st_size,a["size"]) if partial.exists() else 0
        need+=a["size"]-have
    return need
def physical_memory():
    import ctypes
    from ctypes import wintypes
    class Status(ctypes.Structure):
        _fields_=[("length",wintypes.DWORD),("load",wintypes.DWORD)]+[(name,ctypes.c_ulonglong) for name in
            ["total","available","page_total","page_available","virtual_total","virtual_available","extended"]]
    status=Status();status.length=ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):raise OSError("无法读取内存容量")
    return status.total
def install(args):
    from configure_local_ai import configure
    lock = read_json(REPO / "deployment/models.lock.json")
    root = checked_root(args.ai_root)
    files = lock["model"]["files"]
    reuse = reuse_candidates(args.reuse_models)
    need=remaining_weight_bytes(root,files,reuse)
    plan = dict(ai_root=str(root), model=lock["model"]["name"], quantization=lock["model"]["quantization"],
                total_model_bytes=sum(a["size"] for a in files), maximum_new_weight_bytes=need,
                source=lock["strata"]["commit"], native_vision=True, port=lock["model"]["port"])
    print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
    if args.plan: return
    if os.name != "nt": raise RuntimeError("本地模型安装仅适用于 Windows NVIDIA")
    hardware = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                              check=True, capture_output=True, text=True)
    print(hardware.stdout, flush=True)
    first = hardware.stdout.splitlines()[0].split(",")
    if int(first[1].strip().split()[0]) < 11000: raise RuntimeError("此固定方案需要约12GB以上显存")
    if int(first[2].strip().split(".")[0])<580:raise RuntimeError("CUDA13方案需要R580或更新的兼容NVIDIA驱动；未下载模型")
    ram=physical_memory()
    print("物理内存：%.1f GiB"%(ram/1024**3),flush=True)
    if ram<44*1024**3:raise RuntimeError("本固定方案以48GB物理内存为基线；未开始下载模型")
    root.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(root).free < need + 4 * 1024**3:
        raise RuntimeError("SSD剩余空间不足：需要新权重加至少4GiB安装余量")
    downloads = root / "downloads"; state = REPO / ".local-ai"
    state.mkdir(exist_ok=True); downloads.mkdir(exist_ok=True)
    with install_lock(state):
        receipt_path = state / "download-receipts.json"
        receipts = read_json(receipt_path) if receipt_path.exists() else {}
        try:
            source_zip = download(lock["strata"]["source"], downloads, receipts)
            source_parent = install_archive(source_zip, root / "strata-source", lock["strata"]["source"]["sha256"])
            source = source_parent / ("Strata-" + lock["strata"]["commit"])
            if not (source / "serve/server.py").is_file(): raise ValueError("源码结构不符")
            engine_zip = download(lock["strata"]["engine"], downloads, receipts)
            engine = install_archive(engine_zip, root / "engine-0.1.54", lock["strata"]["engine"]["sha256"])
            python = root / "strata-venv/Scripts/python.exe"
            if not python.exists(): run([sys.executable, "-m", "venv", python.parents[1]])
            run([python, "-m", "pip", "install", "-r", source / "requirements.txt"])
            model_root = root / "models"
            for a in files:
                dest = model_root / a["group"] / a["filename"]; dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    candidates = [p for p in reuse.get(a["filename"], []) if p.stat().st_size == a["size"]]
                    if candidates:
                        original = candidates[0]
                        if sha256(original) != a["sha256"]: raise ValueError("复用模型SHA256不符：" + str(original))
                        try: os.link(original, dest)
                        except OSError as exc: raise RuntimeError("复用采用硬链接，AiRoot与原模型须在同一磁盘；未复制大文件") from exc
                        info = dest.stat()
                        receipts[str(dest.resolve())] = dict(size=info.st_size,mtime_ns=info.st_mtime_ns,sha256=a["sha256"])
                download(a, dest.parent, receipts, args.hf_endpoint)
                atomic(receipt_path, receipts)
            pack = root / "packs/deepseek41-native"
            run([python] + pack_arguments(source, model_root, pack, files))
            hot = source / "data/dsv41/profile-2.25.bin"
            if hot.exists(): shutil.copy2(hot, pack / "expert-profile.bin")
            exes = list(engine.rglob("strata-dsv41.exe"))
            if len(exes) != 1: raise ValueError("引擎文件结构不符")
            run([exes[0], "--pack-info", "--pack", pack])
            configure(root, source, python, exes[0], pack, apply_bot=True)
            atomic(state / "installation.json", dict(**plan, completed=True))
            print("本地模型安装完成；运行 start-all.cmd 启动。请先登录QQ、配置自己的昵称和监听名单。", flush=True)
        finally: atomic(receipt_path, receipts)
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ai-root", default="D:/QQWhaleAI")
    p.add_argument("--reuse-models", type=Path)
    p.add_argument("--hf-endpoint", default=os.environ.get("HF_ENDPOINT"))
    p.add_argument("--plan", action="store_true")
    args = p.parse_args()
    try: install(args)
    except (OSError,ValueError,RuntimeError,subprocess.CalledProcessError) as exc:
        print("安装未完成：" + str(exc), file=sys.stderr); return 1
    return 0
if __name__ == "__main__": sys.exit(main())
