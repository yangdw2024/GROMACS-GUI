#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自绘实时曲线控件（CurveWidget）
"""

from PyQt5.QtWidgets import QWidget, QSizePolicy


from PyQt5.QtCore import Qt, QRect, QPointF


from PyQt5.QtGui import QFont, QColor, QPainter, QPen


# =============================================================================
# 自绘曲线控件
# =============================================================================
class CurveWidget(QWidget):
    def __init__(self, parent=None, y_label="", color=QColor(255, 0, 0)):
        super().__init__(parent)
        self._data = []
        self._y_label = y_label
        self._color = color
        self._min_y = None
        self._max_y = None
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def add_point(self, time_val, value):
        self._data.append((float(time_val), float(value)))
        self._update_y_range()
        self.update()

    def clear(self):
        self._data = []
        self._min_y = None
        self._max_y = None
        self.update()

    def _update_y_range(self):
        if not self._data:
            return
        values = [v for _, v in self._data]
        self._min_y = min(values)
        self._max_y = max(values)
        if self._min_y == self._max_y:
            self._min_y -= 1.0
            self._max_y += 1.0
        margin = (self._max_y - self._min_y) * 0.1
        self._min_y -= margin
        self._max_y += margin

    def get_last_value(self):
        if self._data:
            return self._data[-1][1]
        return None

    def paintEvent(self, event):
        if self.width() <= 0 or self.height() <= 0:
            return

        painter = QPainter(self)
        if not painter.isActive():
            return

        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            rect = self.rect()
            margin_left = 70
            margin_right = 20
            margin_top = 25
            margin_bottom = 35
            plot_rect = QRect(margin_left, margin_top,
                              max(1, rect.width() - margin_left - margin_right),
                              max(1, rect.height() - margin_top - margin_bottom))

            painter.fillRect(rect, QColor(255, 255, 255))

            painter.setPen(QColor(200, 200, 200))
            painter.drawRect(plot_rect)

            if self._data and self._min_y is not None and self._max_y is not None:
                n_grid = 5
                for i in range(n_grid + 1):
                    y = plot_rect.top() + plot_rect.height() * i / n_grid
                    painter.setPen(QColor(230, 230, 230))
                    painter.drawLine(plot_rect.left(), int(y), plot_rect.right(), int(y))
                    val = self._max_y - (self._max_y - self._min_y) * i / n_grid
                    painter.setPen(QColor(80, 80, 80))
                    painter.setFont(QFont("Arial", 8))
                    painter.drawText(QRect(5, int(y) - 10, margin_left - 10, 20),
                                     Qt.AlignRight | Qt.AlignVCenter,
                                     f"{val:.2f}")

                times = [t for t, _ in self._data]
                min_t = min(times)
                max_t = max(times)
                if min_t == max_t:
                    max_t = min_t + 1.0
                for i in range(n_grid + 1):
                    x = plot_rect.left() + plot_rect.width() * i / n_grid
                    painter.setPen(QColor(230, 230, 230))
                    painter.drawLine(int(x), plot_rect.top(), int(x), plot_rect.bottom())
                    t_val = min_t + (max_t - min_t) * i / n_grid
                    painter.setPen(QColor(80, 80, 80))
                    painter.setFont(QFont("Arial", 8))
                    painter.drawText(QRect(int(x) - 30, plot_rect.bottom() + 5, 60, 20),
                                     Qt.AlignCenter,
                                     f"{t_val:.1f}")

                painter.setPen(QColor(50, 50, 50))
                painter.setFont(QFont("Arial", 9, QFont.Bold))
                painter.drawText(QRect(plot_rect.left(), 2, plot_rect.width(), 20),
                                 Qt.AlignCenter, self._y_label)

                painter.setPen(QColor(60, 60, 60))
                painter.setFont(QFont("Arial", 8))
                painter.drawText(QRect(plot_rect.left(), plot_rect.bottom() + 20,
                                       plot_rect.width(), 15),
                                 Qt.AlignCenter, "时间 (ps)")

                pen = QPen(self._color)
                pen.setWidth(2)
                painter.setPen(pen)
                points = []
                for t, v in self._data:
                    x = plot_rect.left() + (t - min_t) / (max_t - min_t) * plot_rect.width()
                    y = plot_rect.bottom() - (v - self._min_y) / (self._max_y - self._min_y) * plot_rect.height()
                    points.append(QPointF(x, y))

                if len(points) >= 2:
                    for i in range(len(points) - 1):
                        painter.drawLine(points[i], points[i + 1])
                elif len(points) == 1:
                    painter.setBrush(self._color)
                    painter.drawEllipse(points[0], 3, 3)

                if self._data:
                    last_t, last_v = self._data[-1]
                    painter.setPen(QColor(40, 40, 40))
                    painter.setFont(QFont("Arial", 9, QFont.Bold))
                    text = f"当前: {last_v:.3f}"
                    painter.drawText(QRect(plot_rect.right() - 120, 2, 115, 20),
                                     Qt.AlignRight | Qt.AlignVCenter, text)
            else:
                painter.setPen(QColor(150, 150, 150))
                painter.setFont(QFont("Arial", 10))
                painter.drawText(plot_rect, Qt.AlignCenter, "暂无数据")
                painter.setPen(QColor(50, 50, 50))
                painter.setFont(QFont("Arial", 9, QFont.Bold))
                painter.drawText(QRect(plot_rect.left(), 2, plot_rect.width(), 20),
                                 Qt.AlignCenter, self._y_label)
        finally:
            painter.end()
