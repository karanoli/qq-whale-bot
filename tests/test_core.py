import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import memory
from direct_reader import DirectStream
from memory import Memory
from reasoning import choose
from reply_text import clean_reply
from runtime import load_config, chat_payload, api_headers
from storage import rotate_log

ROOT = Path(__file__).resolve().parents[1]


def temporary():
    return tempfile.TemporaryDirectory(dir=os.environ.get('QQ_BOT_TEST_TMP'))


def row(ident, body='消息', own=False, sender='测试用户'):
    return dict(id=ident, sender=sender, body=body, self=own, images=[],
                image_count=0, time=time.strftime('%Y-%m-%d %H:%M:%S'))


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = temporary()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scope = patch.object(memory, 'ROOT', self.root)
        self.scope.start()
        self.addCleanup(self.scope.stop)
        self.target = dict(kind='group', id='12345', name='测试群')

    def test_scopes_are_separate(self):
        a = Memory(self.target)
        a.merge([row('one', '只在第一个群')])
        b = Memory(dict(kind='group', id='23456', name='另一个测试群'))
        self.assertEqual(b.data['messages'], [])
        self.assertEqual(len(Memory(self.target).data['messages']), 1)

    def test_private_and_group_with_same_number_are_separate(self):
        a = Memory(self.target)
        a.merge([row('one')])
        b = Memory(dict(self.target, kind='private'))
        self.assertEqual(b.data['messages'], [])

    def test_baseline_and_duplicate_are_not_pending(self):
        m = Memory(self.target)
        m.merge([row('one')], baseline=True)
        m.merge([row('one')])
        self.assertEqual(m.data['pending'], [])
        m.merge([row('one'), row('two')])
        self.assertEqual(m.data['pending'], ['two'])

    def test_own_messages_are_not_new_requests(self):
        m = Memory(self.target)
        m.merge([row('own', own=True)])
        self.assertEqual(m.data['pending'], [])

    def test_image_path_and_description_survive_text_poll(self):
        m = Memory(self.target)
        image = row('picture', '[图片，尚未获取内容]')
        image.update(image_count=1, images=['local.jpg'], vision=['红色圆形'])
        m.merge([image])
        m.merge([dict(image, images=[])])
        saved = m.data['messages'][0]
        self.assertEqual(saved['images'], ['local.jpg'])
        self.assertEqual(saved['vision'], ['红色圆形'])
        self.assertIn('红色圆形', m.render(saved))
        self.assertNotIn('尚未获取内容', m.render(saved))

    def test_unread_image_is_explicit(self):
        m = Memory(self.target)
        image = dict(row('picture'), image_count=1)
        self.assertIn('图片未读到', m.render(image))

    def test_context_removes_assistant_timestamp(self):
        m = Memory(self.target)
        m.merge([row('own', '[2026-01-01 10:00:00] 饭呢', own=True)], baseline=True)
        m.merge([row('new', '你好')])
        context = m.context()
        self.assertEqual(context[0], dict(role='assistant', content='饭呢'))
        self.assertIn('本轮新消息', context[-1]['content'])

    def test_send_attempt_persists_until_confirmed(self):
        m = Memory(self.target)
        m.merge([row('question')])
        m.record_attempt('回答', ['question'])
        saved = Memory(self.target)
        self.assertEqual(saved.data['pending'], [])
        self.assertEqual(saved.data['messages'][-1]['delivery'], 'uncertain')
        own = row('confirmed', '回答', own=True, sender='小鲸')
        saved.remember_sent([own], '回答')
        self.assertFalse(any(x.get('delivery') == 'uncertain' for x in saved.data['messages']))
        self.assertEqual(sum(x['body'] == '回答' for x in saved.data['messages']), 1)

    def test_retention_is_bounded(self):
        m = Memory(self.target)
        m.merge([row(str(i)) for i in range(4105)])
        self.assertEqual(len(m.data['messages']), 60)
        self.assertEqual(len(m.data['seen']), 4000)
        self.assertLessEqual(len(m.data['pending']), 200)

    def test_rejects_bad_scope(self):
        with self.assertRaises(ValueError):
            Memory(dict(self.target, id='../bad'))


class StreamTests(unittest.TestCase):
    def setUp(self):
        self.tmp = temporary()
        self.addCleanup(self.tmp.cleanup)
        self.stream = DirectStream(self.tmp.name, {})

    def test_new_message_keeps_old_ids(self):
        first = self.stream.merge([row('unused', '第一条')])
        self.assertTrue(self.stream.baseline)
        second = self.stream.merge([row('unused', '第一条'), row('unused', '第二条')])
        self.assertFalse(self.stream.baseline)
        self.assertEqual(first[0]['id'], second[0]['id'])
        self.assertNotEqual(second[0]['id'], second[1]['id'])

    def test_missing_overlap_rebases(self):
        self.stream.merge([row('unused', '旧历史')])
        self.stream.merge([row('unused', '完全不同的历史')])
        self.assertTrue(self.stream.baseline)

    def test_ambiguous_duplicate_images_rebase_instead_of_replaying(self):
        picture = dict(row('unused', '[图片]'), image_count=1)
        self.stream.merge([picture])
        self.stream.merge([picture, picture])
        self.assertTrue(self.stream.baseline)


class ConfigTests(unittest.TestCase):
    def config_file(self):
        temp = temporary()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / 'config.json'
        cfg = json.loads((ROOT / 'config.example.json').read_text(encoding='utf-8'))
        path.write_text(json.dumps(cfg), encoding='utf-8-sig')
        return path

    def test_relative_paths_follow_config_location(self):
        path = self.config_file()
        cfg = load_config(path)
        self.assertEqual(Path(cfg['persona']), path.parent / 'personality.md')
        self.assertEqual(Path(cfg['vision']['allowed_roots'][0]), path.parent / 'conversations')

    def test_empty_self_names_rejected(self):
        path = self.config_file()
        cfg = json.loads(path.read_text(encoding='utf-8-sig'))
        cfg['self_names'] = []
        path.write_text(json.dumps(cfg), encoding='utf-8')
        with self.assertRaises(ValueError):
            load_config(path)

    def test_standard_request_omits_server_specific_parameters(self):
        profile = dict(max_tokens=100, effort='medium', reasoning_budget_tokens=30)
        cfg = dict(model='test')
        payload = chat_payload(cfg, [], profile)
        self.assertNotIn('reasoning_effort', payload)
        self.assertNotIn('reasoning_budget_tokens', payload)

    def test_extended_request_is_opt_in(self):
        profile = dict(max_tokens=100, effort='high', reasoning_budget_tokens=30)
        payload = chat_payload(dict(model='test', send_reasoning_parameters=True), [], profile)
        self.assertEqual(payload['reasoning_budget_tokens'], 30)

    def test_key_is_read_from_environment(self):
        with patch.dict(os.environ, {'QQ_BOT_TEST_KEY': 'test-value'}):
            self.assertEqual(api_headers(dict(api_key_env='QQ_BOT_TEST_KEY')),
                             {'Authorization': 'Bearer test-value'})


class TextTests(unittest.TestCase):
    def test_removes_only_leading_timestamps(self):
        self.assertEqual(clean_reply('[2026-01-01 10:00] [2026-01-01 10:01:02] 你好'), '你好')
        self.assertEqual(clean_reply('约在[2026-01-01 10:00]见'), '约在[2026-01-01 10:00]见')

    def test_rejects_nontext(self):
        with self.assertRaises(ValueError):
            clean_reply(None)

    def test_reasoning_profiles(self):
        class M:
            def __init__(self, text):
                self.data = dict(messages=[row('x', text)], pending=['x'])
            def is_self(self, value):
                return value['self']
        self.assertEqual(choose(M('白饭呢'), {})['effort'], 'medium')
        self.assertEqual(choose(M('请证明整数的性质'), {})['effort'], 'high')
        self.assertEqual(choose(M('不要高档思考，随便聊聊'), {})['effort'], 'medium')


class StorageTests(unittest.TestCase):
    def test_log_rotation_preserves_recent_archives(self):
        with temporary() as directory:
            path = Path(directory) / 'bot-log.jsonl'
            with patch('storage.MAX_LOG_BYTES', 4):
                for i in range(5):
                    path.write_text(str(i) * 8, encoding='utf-8')
                    rotate_log(path)
            self.assertTrue(Path(str(path) + '.1').exists())
            self.assertTrue(Path(str(path) + '.3').exists())
            self.assertFalse(Path(str(path) + '.4').exists())

    def test_reset_preserves_configuration_and_caps_backups(self):
        spec = importlib.util.spec_from_file_location('reset_memory', ROOT / 'reset-memory.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with temporary() as directory:
            root = Path(directory)
            (root / 'config.json').write_text('{}', encoding='utf-8')
            (root / 'personality.md').write_text('人格', encoding='utf-8')
            for i in range(4):
                folder = root / 'conversations'
                folder.mkdir()
                (folder / 'memory.json').write_text(str(i), encoding='utf-8')
                module.reset_files(root)
            self.assertEqual((root / 'personality.md').read_text(encoding='utf-8'), '人格')
            self.assertTrue((root / 'config.json').exists())
            self.assertFalse((root / 'conversations').exists())
            self.assertEqual(len(list((root / 'memory-backups').iterdir())), 3)


if __name__ == '__main__':
    unittest.main()
