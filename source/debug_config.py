#!/usr/bin/env python3
from core import ConfigManager

cfg = ConfigManager()

def callback(k, v):
    print(f'CALLBACK: key={k}, value={v}')

print(f'listeners before: {cfg._listeners}')
cfg.add_listener('test', callback)
print(f'listeners after add: {cfg._listeners}')
print('setting test.key2...')
cfg.set('test.key2', 'value2')
print(f'listeners after set: {cfg._listeners}')
print('done')
