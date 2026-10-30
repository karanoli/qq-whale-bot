import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import sys
import unittest
import zipfile
import requests
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"deployment"))
from install_local_ai import download,extract_checked,checked_root,remaining_weight_bytes,pack_arguments
def temporary():return tempfile.TemporaryDirectory(dir=os.environ.get("QQ_BOT_TEST_TMP"))

DATA=b"pinned reproducible asset"*100
class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp=temporary();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)
        self.requests=[]
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                header=self.headers.get("Range");owner.requests.append(header)
                start=int(header.split("=")[1].split("-")[0]) if header else 0
                if self.path=="/ignore":start=0
                self.send_response(206 if start else 200)
                if start:self.send_header("Content-Range","bytes %d-%d/%d"%(start,len(DATA)-1,len(DATA)))
                self.send_header("Content-Length",str(len(DATA)-start));self.end_headers();self.wfile.write(DATA[start:])
            def log_message(self,*args):pass
        self.server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        self.session=requests.Session();self.session.trust_env=False;self.addCleanup(self.session.close)
    def asset(self,path="/range"):
        return dict(filename="asset.dat",url="http://127.0.0.1:%d%s"%(self.server.server_port,path),size=len(DATA),sha256=hashlib.sha256(DATA).hexdigest())
    def test_resume_and_verified_receipt_skips_redownload(self):
        (self.path/"asset.dat.part").write_bytes(DATA[:123])
        receipts={};p=download(self.asset(),self.path,receipts,session=self.session)
        self.assertEqual(p.read_bytes(),DATA);self.assertEqual(self.requests,["bytes=123-"])
        download(self.asset(),self.path,receipts,session=self.session)
        self.assertEqual(len(self.requests),1)
    def test_server_ignoring_range_restarts_instead_of_appending(self):
        (self.path/"asset.dat.part").write_bytes(DATA[:80])
        p=download(self.asset("/ignore"),self.path,{},session=self.session)
        self.assertEqual(p.read_bytes(),DATA)
    def test_bad_hash_is_not_installed(self):
        a=self.asset();a["sha256"]="0"*64
        with self.assertRaises(ValueError):download(a,self.path,{},session=self.session)
        self.assertFalse((self.path/"asset.dat").exists())
    def test_existing_wrong_file_not_overwritten(self):
        p=self.path/"asset.dat";p.write_bytes(b"wrong")
        with self.assertRaises(ValueError):download(self.asset(),self.path,{},session=self.session)
        self.assertEqual(p.read_bytes(),b"wrong")

class InstallPlanTests(unittest.TestCase):
    def test_resume_disk_estimate_counts_only_remaining_bytes(self):
        with temporary() as d:
            root=Path(d);p=root/"models/backbone/x.gguf.part";p.parent.mkdir(parents=True);p.write_bytes(b"x"*60)
            self.assertEqual(remaining_weight_bytes(root,[dict(group="backbone",filename="x.gguf",size=100)],{}),40)
    def test_root_and_repository_are_protected(self):
        with temporary() as d:
            repo=Path(d)
            with self.assertRaises(ValueError):checked_root(repo,repo)
            with self.assertRaises(ValueError):checked_root(repo/"models",repo)
            self.assertEqual(checked_root(repo/".local-ai/models",repo),(repo/".local-ai/models").resolve())
    def test_archive_traversal_is_rejected_before_extraction(self):
        with temporary() as d:
            root=Path(d);p=root/"bad.zip"
            with zipfile.ZipFile(p,"w") as z:z.writestr("../escape.txt","bad")
            with self.assertRaises(ValueError):extract_checked(p,root/"out")
            self.assertFalse((root/"escape.txt").exists())
    def test_pack_recipe_keeps_metadata_out_of_engram_directory(self):
        lock=json.loads((ROOT/"deployment/models.lock.json").read_text())
        args=pack_arguments(Path("source"),Path("models"),Path("pack"),lock["model"]["files"])
        self.assertEqual(args[args.index("--engram")+1],str(Path("models/engram")))
        self.assertIn(str(Path("models/shared")/"DeepSeek-V4.1-Flash-1017-UD-Q8_K_XL-00001-of-00009.gguf"),args)
        self.assertEqual(args[args.index("--dspark-noise-token")+1],"128799")
        self.assertEqual(len(args[args.index("--shards")+1:]),4)
    def test_lock_is_complete_and_pinned(self):
        lock=json.loads((ROOT/"deployment/models.lock.json").read_text())
        self.assertEqual(lock["strata"]["tag"],"v0.2.8")
        self.assertEqual(len(lock["model"]["files"]),8)
        for a in lock["model"]["files"]:
            self.assertEqual(len(a["sha256"]),64);self.assertGreater(a["size"],0)
            self.assertRegex(a["url"],r"/resolve/[0-9a-f]{40}/")
if __name__=="__main__":unittest.main()
