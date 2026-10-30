"""Read-only installation and model-service checks."""
import argparse
import importlib.util
import json
import sys
import urllib.request
from urllib.parse import urlparse
from runtime import load_config, api_headers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--services-only', action='store_true')
    args = parser.parse_args()
    cfg = load_config()
    errors = []
    if not args.services_only:
        if sys.platform != 'win32':
            errors.append('桌面机器人只能运行在 Windows；Mac 可编辑源码和运行核心测试。')
        for name in ['requests', 'win32gui', 'cv2', 'PIL', 'numpy', 'onnxruntime', 'rapidocr_onnxruntime', 'tkinter']:
            if importlib.util.find_spec(name) is None:
                errors.append('缺少依赖：' + name)
    services = [('聊天', cfg)]
    if cfg.get('vision', {}).get('enabled'):
        services.append(('识图', cfg['vision']))
    for label, service in services:
        endpoint = service.get('endpoint', '')
        if not endpoint.endswith('/chat/completions'):
            errors.append(label + ' endpoint 应以 /chat/completions 结尾。')
            continue
        if label == '识图' and urlparse(endpoint).hostname not in ('127.0.0.1', 'localhost', '::1'):
            errors.append('识图服务目前只支持本机地址。')
            continue
        url = endpoint[:-len('/chat/completions')] + '/models'
        try:
            request = urllib.request.Request(url, headers=api_headers(service))
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=8) as response:
                data = json.load(response)
            if not isinstance(data, dict):
                raise ValueError('模型列表格式不正确')
            print(label + '模型接口可访问。请确认 config.json 的 model 与服务端一致。')
        except Exception as exc:
            errors.append(label + '模型服务不可用：' + type(exc).__name__)
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as exc:
        print(str(exc))
        sys.exit(1)
