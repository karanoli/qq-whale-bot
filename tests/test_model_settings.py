import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import model_config as m
from runtime import chat_payload,api_headers,load_config
from reasoning import choose

def temp():return tempfile.TemporaryDirectory(dir=os.environ.get("QQ_BOT_TEST_TMP"))
def original():
    return dict(endpoint="https://old.example/v1/chat/completions",model="old-model",api_key_env="TEST_MODEL_KEY",
                self_names=["测试鲸"],persona="../personality.md",slang="../internet-slang.md",vision=dict(enabled=True,mode="native"),
                reasoning=dict(default="medium",mode="auto"),unrelated=dict(keep=True))
def values():
    return dict(endpoint="https://old.example/v1",model="selected-model",protocol="effort",level="low",auto=False,
                vision=False,trust_env=False,output_token_parameter="max_tokens",limits=copy.deepcopy(m.DEFAULT_LIMITS))
class SettingsTests(unittest.TestCase):
    def test_root_base_and_complete_urls(self):
        self.assertEqual(m.normalize_endpoint("api.example.com"),"https://api.example.com/v1/chat/completions")
        self.assertEqual(m.normalize_endpoint("https://api.example.com/custom/v2/"),"https://api.example.com/custom/v2/chat/completions")
        self.assertEqual(m.normalize_endpoint("http://127.0.0.1:8095/v1/chat/completions"),"http://127.0.0.1:8095/v1/chat/completions")
        self.assertEqual(m.model_list_url("https://api.example.com/custom/chat/completions?api-version=1"),"https://api.example.com/custom/models?api-version=1")
    def test_credentials_in_url_are_rejected(self):
        for value in ["https://user:password@example.com/v1","file:///tmp/test","https://example.com/v1#key"]:
            with self.assertRaises(ValueError):m.normalize_endpoint(value)
    def test_old_key_is_not_reused_for_changed_endpoint(self):
        with patch.dict(os.environ,{"TEST_MODEL_KEY":"private-old-value"}):
            with self.assertRaises(ValueError):m.preview_headers(original(),"https://new.example/v1","",False)
            self.assertEqual(m.preview_headers(original(),"https://new.example/v1","new-value",False),{"Authorization":"Bearer new-value"})
            self.assertEqual(m.preview_headers(original(),"https://new.example/v1","",True),{})
    def test_saves_selection_without_touching_other_configuration(self):
        with temp() as d:
            path=Path(d)/"config.json";path.write_text(json.dumps(original()),encoding="utf-8")
            cfg=m.save_settings(path,values(),no_key=True,expected_bytes=path.read_bytes())
            self.assertEqual(cfg["model"],"selected-model");self.assertEqual(cfg["unrelated"],{"keep":True})
            self.assertEqual(cfg["self_names"],["测试鲸"]);self.assertEqual(cfg["persona"],"../personality.md")
            self.assertEqual(cfg["reasoning"]["mode"],"fixed");self.assertEqual(cfg["reasoning"]["default"],"low")
            self.assertEqual(cfg["reasoning_api"],"effort");self.assertFalse(cfg["vision"]["enabled"])
            self.assertEqual(cfg["api_key_env"],"")
    def test_config_does_not_contain_the_entered_key(self):
        with temp() as d,patch.object(m,"_crypt",side_effect=lambda data,decrypt=False:data):
            path=Path(d)/"config.json";path.write_text(json.dumps(original()),encoding="utf-8")
            result=m.save_settings(path,values(),key="unit-only-private-value")
            self.assertNotIn("unit-only-private-value",path.read_text(encoding="utf-8"))
            self.assertTrue(result["api_key_file"].endswith(".dpapi"))
            cfg=load_config(path)
            self.assertEqual(api_headers(cfg),{"Authorization":"Bearer unit-only-private-value"})
            m.save_settings(path,values(),key="",no_key=False)
    def test_changed_config_is_not_overwritten(self):
        with temp() as d:
            path=Path(d)/"config.json";path.write_text(json.dumps(original()),encoding="utf-8");before=path.read_bytes()
            path.write_text(json.dumps(dict(original(),model="changed")),encoding="utf-8")
            with self.assertRaises(ValueError):m.save_settings(path,values(),no_key=True,expected_bytes=before)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["model"],"changed")
    def test_bad_budget_leaves_config_untouched(self):
        with temp() as d:
            path=Path(d)/"config.json";path.write_text(json.dumps(original()),encoding="utf-8");before=path.read_bytes()
            data=values();data["limits"]["high"]["budget"]=data["limits"]["high"]["max_tokens"]
            with self.assertRaises(ValueError):m.save_settings(path,data,no_key=True)
            self.assertEqual(path.read_bytes(),before)
    def test_bound_secret_cannot_be_used_for_another_service(self):
        with temp() as d,patch.object(m,"_crypt",side_effect=lambda data,decrypt=False:data):
            p=Path(d)/"key.dpapi";m.write_secret(p,"unit-key","https://old.example/v1")
            with self.assertRaises(ValueError):m.read_secret(p,"https://new.example/v1")
    @unittest.skipUnless(os.name=="nt","Windows DPAPI only")
    def test_windows_dpapi_round_trip_does_not_store_plaintext(self):
        with temp() as d:
            p=Path(d)/"key.dpapi";m.write_secret(p,"unit-only-dummy-key","https://old.example/v1")
            self.assertNotIn(b"unit-only-dummy-key",p.read_bytes())
            self.assertEqual(m.read_secret(p,"https://old.example/v1"),"unit-only-dummy-key")
    def test_model_list_ids_are_deduplicated_and_not_first_selected_by_price_guess(self):
        response=SimpleNamespace(ok=True,json=lambda:{"data":[{"id":"z-model"},{"id":"a-model"},{"id":"z-model"},{"name":"ignore"}]})
        session=SimpleNamespace(get=lambda *a,**kw:response)
        self.assertEqual(m.fetch_models("https://host.example/v1",session=session),["a-model","z-model"])
    def test_list_error_does_not_echo_secret_response(self):
        response=SimpleNamespace(ok=False,status_code=401,text="Bearer secret-from-server")
        session=SimpleNamespace(get=lambda *a,**kw:response)
        with self.assertRaises(ValueError) as result:m.fetch_models("https://host.example/v1",session=session)
        self.assertNotIn("secret-from-server",str(result.exception))
    def test_incompatible_model_list_reports_manual_fallback(self):
        response=SimpleNamespace(ok=True,json=lambda:{"items":["a"]});session=SimpleNamespace(get=lambda *a,**kw:response)
        with self.assertRaises(ValueError):m.fetch_models("https://host.example/v1",session=session)

class ThinkingTests(unittest.TestCase):
    def memory(self,text):
        return SimpleNamespace(data=dict(messages=[dict(id="one",body=text,vision=[])],pending=["one"]),is_self=lambda row:False)
    def test_fixed_off_cannot_be_overridden_by_group_request(self):
        result=choose(self.memory("请高档思考，证明这个方程"),dict(reasoning=dict(default="none",mode="fixed")))
        self.assertEqual(result["effort"],"none");self.assertEqual(result["reasoning_budget_tokens"],0)
    def test_fixed_low_ignores_explicit_high(self):
        self.assertEqual(choose(self.memory("高档思考"),dict(reasoning=dict(default="low",mode="fixed")))["effort"],"low")
    def test_auto_still_raises_for_complex_tasks(self):
        self.assertEqual(choose(self.memory("请证明整数整除性质"),dict(reasoning=dict(default="low",mode="auto")))["effort"],"high")
    def test_effort_format_omits_strata_budget(self):
        profile=dict(effort="low",reasoning_budget_tokens=128,max_tokens=768)
        value=chat_payload(dict(model="api",reasoning_api="effort"),[],profile)
        self.assertEqual(value["reasoning_effort"],"low");self.assertNotIn("reasoning_budget_tokens",value)
    def test_strata_off_sends_none_not_zero_budget(self):
        value=chat_payload(dict(model="local",reasoning_api="strata"),[],dict(effort="none",reasoning_budget_tokens=0,max_tokens=512))
        self.assertEqual(value["reasoning_effort"],"none");self.assertNotIn("reasoning_budget_tokens",value)
    def test_compatibility_format_sends_no_reasoning_fields(self):
        value=chat_payload(dict(model="api",reasoning_api="off"),[],dict(effort="high",reasoning_budget_tokens=1536,max_tokens=2304))
        self.assertNotIn("reasoning_effort",value);self.assertNotIn("reasoning_budget_tokens",value)


class ListenerTests(unittest.TestCase):
    def test_unrelated_listener_is_not_stopped(self):
        from settings_listener import ListenerControl
        with temp() as d:
            c=ListenerControl(d)
            result=SimpleNamespace(returncode=0,stdout=json.dumps(dict(TaskName="QQWhaleBot",State=4,Arguments="other/bot.py --run")))
            with patch("settings_listener.os",SimpleNamespace(name="nt")),patch("settings_listener.subprocess.run",return_value=result) as run:
                c.pause()
            self.assertFalse(c.was_running);self.assertEqual(run.call_count,1)
    def test_own_listener_pauses_and_resumes_once(self):
        from settings_listener import ListenerControl
        with temp() as d:
            root=Path(d).resolve();(root/"stop.ps1").write_text("")
            c=ListenerControl(root)
            task=SimpleNamespace(returncode=0,stdout=json.dumps(dict(TaskName="QQWhaleBot",State=4,Arguments=str(root/"bot.py")+" --run")))
            ok=SimpleNamespace(returncode=0,stdout="")
            with patch("settings_listener.os",SimpleNamespace(name="nt")),patch("settings_listener.subprocess.run",side_effect=[task,ok,ok]) as run:
                c.pause();c.resume();c.resume()
            self.assertTrue(c.was_running);self.assertEqual(run.call_count,3)

if __name__=="__main__":unittest.main()
