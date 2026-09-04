#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from source.core.config_manager import ConfigManager
from source.core.logger import AppLogger
from source.core.error_handler import ErrorHandler
from source.core.resource_monitor import ResourceMonitor
from source.core.event_bus import EventBus
from source.core.review_mechanism import ReviewMechanism, ReviewLevel
from source.core.correction_mechanism import CorrectionMechanism
from source.core.audit_mechanism import AuditMechanism, AuditActionType
from source.core.auto_updater import AutoUpdater

print('=== Trae Framework v4.2.0 综合测试 ===')

cm = ConfigManager()
print('OK ConfigManager:', cm.get('test.key'))

logger = AppLogger('TestApp')
logger.info('Logger test')
print('OK AppLogger')

eh = ErrorHandler()
print('OK ErrorHandler')

rm = ResourceMonitor()
status = rm.get_status()
print('OK ResourceMonitor: CPU=%d cores, Memory=%.1fGB' % (status.cpu_cores, status.memory_total_gb))

cpu_info = rm.get_cpu_info()
print('  CPU: %s, Cores: %d, Threads: %d' % (cpu_info['name'], cpu_info['cores'], cpu_info['threads']))

eb = EventBus()
eb.subscribe('test.*', lambda event: print('  Event:', event.event_type))
eb.publish('test.event', {'data': 'value'})
print('OK EventBus')

review = ReviewMechanism()
result = review.preflight_check('test_task', {'nt': 4}, '.', ReviewLevel.QUICK)
print('OK ReviewMechanism:', result.overall_status.value)

correction = CorrectionMechanism()
print('OK CorrectionMechanism')

audit = AuditMechanism()
audit.log_action(AuditActionType.CONFIG_CHANGE, 'Test action', {'detail': 'Test detail'})
print('OK AuditMechanism:', audit.get_statistics())

updater = AutoUpdater()
print('OK AutoUpdater:', updater.check_for_update())

print('')
print('=== 所有框架模块测试通过 ===')