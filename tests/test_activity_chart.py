"""Verify the actual painter bounds used for chart axis labels."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFontDatabase, QPainter
from PySide6.QtWidgets import QApplication

from app.ui.components import ActivityChart


class ActivityChartAxisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        for filename in ("segoeui.ttf", "msyh.ttc"):
            font_path = Path("C:/Windows/Fonts") / filename
            if font_path.exists():
                QFontDatabase.addApplicationFont(str(font_path))

    def axis_draws(self, chart):
        draws = []
        original = QPainter.drawText

        def record(painter, *args):
            if len(args) == 3 and isinstance(args[0], QRectF):
                draws.append((QRectF(args[0]), args[2]))
            return original(painter, *args)

        with patch.object(QPainter, "drawText", record):
            image = chart.grab().toImage()
        self.assertFalse(image.isNull())
        return draws

    def test_month_dates_have_enough_room_for_every_digit(self):
        chart = ActivityChart()
        try:
            chart.resize(810, 140)
            chart.setStyleSheet("font-family: 'Segoe UI'; font-size: 13px;")
            chart.set_days([(f"10/{day:02}", day * 60) for day in range(1, 32)])
            labels = self.axis_draws(chart)
            self.assertIn("10/16", [text for _, text in labels])
            for rect, text in labels:
                with self.subTest(label=text):
                    self.assertGreaterEqual(rect.width(), chart.fontMetrics().horizontalAdvance(text))
                    self.assertGreaterEqual(rect.height(), chart.fontMetrics().height())
        finally:
            chart.deleteLater()

    def test_labels_fit_inside_narrow_charts_without_overlap(self):
        for width, font_size, texts in (
            (320, 13, [f"10/{day:02}" for day in range(1, 32)]),
            (480, 18, [f"10/{day:02}" for day in range(1, 32)]),
            (240, 22, [f"2026/{month:02}" for month in range(1, 8)]),
        ):
            with self.subTest(width=width, font_size=font_size):
                chart = ActivityChart()
                try:
                    chart.resize(width, 140)
                    chart.setStyleSheet(f"font-family: 'Segoe UI'; font-size: {font_size}px;")
                    chart.set_days([(text, 3600) for text in texts])
                    labels = self.axis_draws(chart)
                    self.assertEqual(labels[0][1], texts[0])
                    self.assertEqual(labels[-1][1], texts[-1])
                    for rect, text in labels:
                        self.assertGreaterEqual(rect.width(), chart.fontMetrics().horizontalAdvance(text))
                        self.assertTrue(QRectF(chart.rect()).contains(rect), (width, text, rect))
                    for (left, _), (right, _) in zip(labels, labels[1:]):
                        self.assertGreaterEqual(right.left() - left.right(), 6)
                finally:
                    chart.deleteLater()


if __name__ == "__main__":
    unittest.main()
