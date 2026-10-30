import io
import json
import os
from pathlib import Path
import tempfile
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch,MagicMock
from PIL import Image
import memory
from memory import Memory
import native_vision as n
import bridge
from runtime import load_config,chat_payload,api_headers

ROOT=Path(__file__).resolve().parents[1]
def temporary():
    return tempfile.TemporaryDirectory(dir=os.environ.get("QQ_BOT_TEST_TMP"))
def row(ident,body="",images=None):
    return dict(id=ident,sender="测试群友",time="2026-01-01 12:00:00",body=body,
                image_count=1 if images else 0,images=images or [],self=False)

class NativeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=temporary();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.patch=patch.object(memory,"ROOT",self.root)
        self.patch.start();self.addCleanup(self.patch.stop)
        self.m=Memory(dict(kind="group",id="123456789",name="测试群"))
        self.cap=self.m.directory/"captured-images";self.cap.mkdir()
        self.image=self.cap/"test.jpg";Image.new("RGB",(84,84),"red").save(self.image)
    def test_pixels_attached_once_and_old_caption_excluded(self):
        r=row("new","评价一下",[str(self.image)]);r["vision"]=["过期的千问虚构背景"]
        self.m.merge([r]);messages,meta=n.context(self.m)
        raw=json.dumps(messages,ensure_ascii=False)
        self.assertTrue(meta["image_attached"])
        self.assertEqual(raw.count("data:image/jpeg;base64,"),1)
        self.assertNotIn("千问虚构背景",raw)
        self.assertNotIn("base64",json.dumps(self.m.data))
    def test_text_only_mode_does_not_upload_stored_image(self):
        self.m.merge([row("new","这图好看吗",[str(self.image)])])
        out,meta=n.context(self.m,enable_images=False)
        self.assertFalse(meta["image_attached"])
        self.assertNotIn("base64",json.dumps(out))
    def test_failed_new_image_never_borrows_old_image(self):
        self.m.merge([row("old","旧图",[str(self.image)])],baseline=True)
        fresh=row("new","新图是什么");fresh["image_count"]=1
        self.m.merge([fresh]);out,meta=n.context(self.m)
        self.assertFalse(meta["image_attached"])
    def test_followup_can_reference_recent_image_but_unrelated_text_cannot(self):
        self.m.merge([row("old","",[str(self.image)])],baseline=True)
        self.m.merge([row("next","那张图什么梗")])
        self.assertTrue(n.context(self.m)[1]["image_attached"])
        self.m.data["messages"][-1]["body"]="晚饭吃什么"
        self.assertFalse(n.context(self.m)[1]["image_attached"])
    def test_other_scope_and_path_traversal_are_blocked(self):
        other=Memory(dict(kind="group",id="234567890",name="另一个群"))
        with self.assertRaises(ValueError):n.valid_image(self.image,other)
        with self.assertRaises(ValueError):n.valid_image(self.cap/"../../../outside.jpg",self.m)
    def test_digest_retention_and_duplicate_order(self):
        for i in range(40):n.note_image(self.m,dict(image_sha256=str(i)))
        n.note_image(self.m,dict(image_sha256="39"))
        self.assertEqual(len(self.m.data["native_seen_images"]),32)
        self.assertEqual(self.m.data["native_seen_images"][-1],"39")
    def test_sending_one_batch_keeps_newer_pending_messages(self):
        self.m.merge([row("q1","旧问题"),row("q2","新问题")])
        self.m.record_attempt("只回复旧问题",["q1"])
        self.assertEqual(self.m.data["pending"],["q2"])
    def test_silent_marker_not_allowed_as_sent_text(self):
        with self.assertRaises(ValueError):bridge.validate_reply("<NO_REPLY>",{})
        with self.assertRaises(ValueError):bridge.validate_reply("no_reply",{})
        self.assertEqual(bridge.validate_reply("？",{}),"？")
    def test_prompt_contract_uses_only_current_scope(self):
        self.m.merge([row("new","这是什么",[str(self.image)])])
        persona=self.root/"persona.md";persona.write_text("测试人格",encoding="utf-8")
        slang=self.root/"slang.md";slang.write_text("vw50=疯四",encoding="utf-8")
        cfg=dict(model="fake",persona=str(persona),slang=str(slang),vision=dict(enabled=True))
        payload=bridge.request_for(self.m,cfg)
        self.assertEqual(payload["model"],"fake")
        self.assertEqual(payload["messages"][0]["role"],"system")
        self.assertIn("vw50",payload["messages"][0]["content"])
        self.assertNotIn("reasoning_budget_tokens",payload)
        self.assertIn("image_url",json.dumps(payload))
        self.assertEqual(bridge.envelope(self.m)["pending_ids"],["new"])

class APICompatibilityTests(unittest.TestCase):
    def test_slang_resolves_relative_to_config(self):
        with temporary() as d:
            p=Path(d)/"config.json";p.write_text(json.dumps(dict(self_names=["小鲸"])),encoding="utf-8")
            self.assertEqual(Path(load_config(p)["slang"]),Path(d)/"internet-slang.md")
    def test_token_parameter_and_omitted_temperature(self):
        cfg=dict(model="api",temperature=None,output_token_parameter="max_completion_tokens")
        payload=chat_payload(cfg,[],dict(max_tokens=64))
        self.assertEqual(payload["max_completion_tokens"],64)
        self.assertNotIn("max_tokens",payload);self.assertNotIn("temperature",payload)
    def test_invalid_token_parameter_rejected(self):
        with self.assertRaises(ValueError):chat_payload(dict(model="api",output_token_parameter="unknown"),[],dict(max_tokens=1))
    def test_background_task_reads_current_user_key_without_serializing_it(self):
        handle=MagicMock();fake=SimpleNamespace(HKEY_CURRENT_USER=1,OpenKey=MagicMock(return_value=handle),
                                               QueryValueEx=MagicMock(return_value=("registry-value",1)))
        with patch("runtime.os.name","nt"),patch.dict(sys.modules,{"winreg":fake}),patch.dict(os.environ,{},clear=True):
            headers=api_headers(dict(api_key_env="TEST_USER_KEY"))
        self.assertEqual(headers,{"Authorization":"Bearer registry-value"})
        fake.QueryValueEx.assert_called_once()
    def test_keys_do_not_enter_payload(self):
        with patch.dict(os.environ,{"TEST_KEY":"private-value"}):
            cfg=dict(model="api",api_key_env="TEST_KEY")
            self.assertEqual(api_headers(cfg)["Authorization"],"Bearer private-value")
            self.assertNotIn("private-value",json.dumps(chat_payload(cfg,[],dict(max_tokens=1))))

if __name__=="__main__":unittest.main()
