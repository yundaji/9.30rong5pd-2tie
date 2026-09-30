import json
import os
import re
import random
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

POSTS = Path('posts.json')
STATE = Path('state.json')
TOKEN = os.environ.get('BOT_TOKEN', '')
TARGET = os.environ.get('TARGET_CHAT', '')
SOURCE = os.environ.get('SOURCE_CHAT', TARGET)


def api(method, payload):
    request = urllib.request.Request(
        f'https://api.telegram.org/bot{TOKEN}/{method}',
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'{method}: HTTP {exc.code}: {exc.read().decode("utf-8", "replace")}') from exc
    if not result.get('ok'):
        raise RuntimeError(f'{method}: {result.get("description", result)}')
    return result['result']


def publish(post):
    if isinstance(post, int):
        post = {'message_id': post}
    if not isinstance(post, dict):
        raise ValueError('帖子须为数字消息 ID 或对象')
    # 支持手写格式：{"id": 1, "text": "配文", "media": ["https://t.me/channel/123"]}
    if 'media' in post:
        urls = post['media']
        if not isinstance(urls, list) or not urls:
            raise ValueError('media 须为非空链接数组')
        parsed = []
        for url in urls:
            match = re.fullmatch(r'https://t\.me/([A-Za-z][A-Za-z0-9_]{4,31})/(\d+)(?:\?single)?', url)
            if not match:
                raise ValueError(f'无效的 t.me 消息链接：{url}')
            parsed.append((f'@{match.group(1)}', int(match.group(2))))
        channels = {channel.lower() for channel, _ in parsed}
        if len(channels) != 1:
            raise ValueError('同一帖子的 media 必须来自同一个频道')
        source = parsed[0][0]
        ids = [number for _, number in parsed]
        caption = post.get('text', '')
        if not isinstance(caption, str) or len(caption) > 1024:
            raise ValueError('图文配文 text 必须是字符串且不超过 1024 字符')
        if len(ids) == 1:
            payload = {'chat_id': TARGET, 'from_chat_id': source, 'message_id': ids[0]}
            if caption:
                payload['caption'] = caption
            api('copyMessage', payload)
        else:
            result = api('copyMessages', {'chat_id': TARGET, 'from_chat_id': source, 'message_ids': ids})
            if len(result) != len(ids):
                raise RuntimeError('复制消息数量不足，请检查机器人能否访问全部原帖')
            if caption:
                try:
                    api('editMessageCaption', {'chat_id': TARGET, 'message_id': result[0]['message_id'], 'caption': caption})
                except RuntimeError as exc:
                    print(f'相册已复制，但修改配文失败：{exc}', file=sys.stderr)
        return
    if 'message_ids' in post:
        ids = post['message_ids']
        if not isinstance(ids, list) or not 2 <= len(ids) <= 100 or not all(type(x) is int and x > 0 for x in ids):
            raise ValueError('message_ids 须为 2–100 个正整数消息 ID')
        result = api('copyMessages', {'chat_id': TARGET, 'from_chat_id': SOURCE, 'message_ids': ids})
        if len(result) != len(ids):
            raise RuntimeError('相册复制数量不足，请检查机器人是否有权访问全部消息')
    elif 'message_id' in post:
        api('copyMessage', {'chat_id': TARGET, 'from_chat_id': SOURCE, 'message_id': post['message_id']})
    elif 'text' in post:
        api('sendMessage', {'chat_id': TARGET, 'text': post['text']})
    elif 'photo' in post or 'video' in post:
        kind = 'photo' if 'photo' in post else 'video'
        payload = {'chat_id': TARGET, kind: post[kind]}
        if 'caption' in post:
            payload['caption'] = post['caption']
        api('sendPhoto' if kind == 'photo' else 'sendVideo', payload)
    else:
        raise ValueError('帖子缺少 media、message_id、message_ids、text、photo 或 video')


def save(state):
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


CHANNELS_FILE = Path('channels.json')
TIMEZONE = ZoneInfo('Asia/Shanghai')
PER_CHANNEL = 2


def load_channels():
    channels = json.loads(CHANNELS_FILE.read_text(encoding='utf-8-sig'))
    if not isinstance(channels, list) or not channels:
        raise ValueError('channels.json须为非空频道数组')
    if any(not isinstance(c, (str, int)) or isinstance(c, bool) for c in channels):
        raise ValueError('频道必须是@用户名或数字chat_id')
    if any(str(c).startswith('@YOUR_') for c in channels):
        raise ValueError('请先将channels.json示例替换成自己的5个频道')
    if len(set(str(c).lower() for c in channels)) != len(channels):
        raise ValueError('channels.json不能有重复频道')
    return channels


def prepare_day(state, now, channels):
    today = now.date().isoformat()
    count = len(channels) * PER_CHANNEL
    if state.get('date') != today:
        state.update(date=today, sent_today=0, channels=channels,
                     schedule=[random.randrange(480 + i * 900 // count,
                                                480 + (i + 1) * 900 // count)
                               for i in range(count)])
    elif state.get('channels') != channels or len(state.get('schedule', [])) != count:
        raise ValueError('当天频道配置已变更，请恢复原配置，次日再调整；不要删除state.json')
    return state


def main():
    global TARGET
    if not TOKEN:
        raise ValueError('请设置BOT_TOKEN')
    channels = load_channels()
    posts = json.loads(POSTS.read_text(encoding='utf-8-sig'))
    if not isinstance(posts, list) or not posts:
        raise ValueError('posts.json须为非空数组')
    state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {'index': 0, 'date': '', 'sent_today': 0}
    now = datetime.now(TIMEZONE)
    prepare_day(state, now, channels)
    save(state)
    minute = now.hour * 60 + now.minute
    due = sum(t <= minute for t in state['schedule'])
    print('今日计划：' + ', '.join(f'{t // 60:02d}:{t % 60:02d}' for t in state['schedule']), flush=True)
    while state['sent_today'] < due:
        if datetime.now(TIMEZONE).date().isoformat() != state['date']:
            break
        slot = state['sent_today']
        TARGET = channels[slot % len(channels)]
        index = state.get('index', 0) % len(posts)
        print(f'今日第{slot + 1}条 → {TARGET}；帖子{index + 1}/{len(posts)}', flush=True)
        publish(posts[index])
        state['index'] = (index + 1) % len(posts)
        state['sent_today'] += 1
        save(state)
    print(f'今日已发送{state["sent_today"]}/{len(state["schedule"])}条', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'错误：{exc}', file=sys.stderr)
        sys.exit(1)
