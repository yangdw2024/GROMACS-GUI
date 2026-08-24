#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
事件总线系统 - 实现组件间的松耦合通信
借鉴：VS Code EventEmitter、Google Guava EventBus、Qt Signal-Slot机制
"""

import threading
import time
import weakref
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass
from enum import Enum


class EventPriority(Enum):
    HIGHEST = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    LOWEST = 4


@dataclass
class Event:
    event_type: str
    data: Any
    timestamp: float = None
    source: str = ""
    priority: EventPriority = EventPriority.NORMAL

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class EventBus:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._subscribers: Dict[str, List[Dict]] = {}
        self._global_subscribers: List[Dict] = []
        self._lock = threading.Lock()
        self._enabled = True

        self._initialized = True

    def publish(self, event_type: str, data: Any = None, source: str = "",
                priority: EventPriority = EventPriority.NORMAL) -> int:
        if not self._enabled:
            return 0

        event = Event(event_type=event_type, data=data, source=source, priority=priority)

        notified = 0
        handlers = []

        with self._lock:
            for pattern in list(self._subscribers.keys()):
                if self._matches_pattern(pattern, event_type):
                    for sub in self._subscribers[pattern]:
                        handlers.append(sub)

            for sub in self._global_subscribers:
                handlers.append(sub)

        handlers.sort(key=lambda h: h["priority"].value)

        for handler in handlers:
            try:
                callback = handler["callback"]
                if handler["use_weak_ref"]:
                    callback = callback()
                    if callback is None:
                        continue
                callback(event)
                notified += 1
            except Exception as e:
                print(f"[EventBus] 处理事件 {event_type} 时出错: {e}")

        return notified

    def subscribe(self, event_pattern: str, callback: Callable,
                  priority: EventPriority = EventPriority.NORMAL,
                  use_weak_ref: bool = False):
        with self._lock:
            if event_pattern not in self._subscribers:
                self._subscribers[event_pattern] = []

            if use_weak_ref:
                callback_ref = weakref.ref(callback)
            else:
                callback_ref = callback

            self._subscribers[event_pattern].append({
                "callback": callback_ref,
                "priority": priority,
                "use_weak_ref": use_weak_ref,
            })

    def subscribe_global(self, callback: Callable,
                         priority: EventPriority = EventPriority.NORMAL):
        with self._lock:
            self._global_subscribers.append({
                "callback": callback,
                "priority": priority,
                "use_weak_ref": False,
            })

    def unsubscribe(self, event_pattern: str, callback: Callable):
        with self._lock:
            if event_pattern not in self._subscribers:
                return

            self._subscribers[event_pattern] = [
                sub for sub in self._subscribers[event_pattern]
                if not (sub["use_weak_ref"] and sub["callback"]() is callback)
                and sub["callback"] is not callback
            ]

    def unsubscribe_global(self, callback: Callable):
        with self._lock:
            self._global_subscribers = [
                sub for sub in self._global_subscribers
                if sub["callback"] is not callback
            ]

    def _matches_pattern(self, pattern: str, event_type: str) -> bool:
        if pattern == "*":
            return True
        if pattern == event_type:
            return True

        if "*" in pattern:
            parts = pattern.split(".")
            event_parts = event_type.split(".")

            for p, e in zip(parts, event_parts):
                if p != "*" and p != e:
                    return False
            return len(parts) <= len(event_parts)

        return False

    def set_enabled(self, enabled: bool):
        self._enabled = enabled

    def get_subscriber_count(self) -> int:
        with self._lock:
            total = len(self._global_subscribers)
            for pattern in self._subscribers:
                total += len(self._subscribers[pattern])
            return total

    def clear_all(self):
        with self._lock:
            self._subscribers.clear()
            self._global_subscribers.clear()

    def get_registered_patterns(self) -> List[str]:
        with self._lock:
            return list(self._subscribers.keys())


class EventBusMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._event_bus = EventBus()

    def publish_event(self, event_type: str, data: Any = None, source: str = ""):
        self._event_bus.publish(event_type, data, source)

    def subscribe_event(self, event_pattern: str, callback: Callable):
        self._event_bus.subscribe(event_pattern, callback)

    def unsubscribe_event(self, event_pattern: str, callback: Callable):
        self._event_bus.unsubscribe(event_pattern, callback)
