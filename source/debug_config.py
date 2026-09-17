#!/usr/bin/env python3
"""ConfigManager 事件监听调试脚本（需手动运行，导入不执行）"""
from core import ConfigManager


def callback(k, v):
    print(f'CALLBACK: key={k}, value={v}')


def main():
    cfg = ConfigManager()

    print(f'listeners before: {cfg._listeners}')
    cfg.add_listener('test', callback)
    print(f'listeners after add: {cfg._listeners}')
    print('setting test.key2...')
    cfg.set('test.key2', 'value2')
    print(f'listeners after set: {cfg._listeners}')
    print('done')


if __name__ == "__main__":
    main()
