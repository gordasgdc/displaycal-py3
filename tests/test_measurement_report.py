"""Tests for the toolkit-neutral measurement report helpers.

Covers the pure pieces extracted from ``MainFrame.measurement_report_handler`` /
``measurement_report_consumer`` in ``DisplayCAL/measurement_report.py``. No
display or QApplication is needed.
"""

from DisplayCAL import measurement_report as mr


class TestDefaultReportFilename:
    def test_basic(self):
        name = mr.default_report_filename(
            "Measurement", "3.9.16", "DELL U2410", "2026-07-04 12-30"
        )
        assert name == "Measurement Report 3.9.16 - DELL U2410 - 2026-07-04 12-30.html"

    def test_self_check_type(self):
        name = mr.default_report_filename(
            "Self Check", "3.9.16", "DELL U2410", "2026-07-04 12-30"
        )
        assert name.startswith("Self Check Report 3.9.16 - ")

    def test_unsafe_characters_sanitized(self):
        name = mr.default_report_filename(
            "Measurement", "3.9.16", 'DELL:U2410/2*?"<>|', "2026-07-04 12-30"
        )
        # The whole run of unsafe chars collapses to a single underscore.
        assert name == "Measurement Report 3.9.16 - DELL_U2410_2_ - 2026-07-04 12-30.html"

    def test_timestamp_defaults_to_now(self):
        name = mr.default_report_filename("Measurement", "3.9.16", "DELL U2410")
        assert name.startswith("Measurement Report 3.9.16 - DELL U2410 - ")
        assert name.endswith(".html")


class TestResolveQuantizationBits:
    def test_separate_z_argument(self):
        assert mr.resolve_quantization_bits(["-v", "-Z", "10", "-d1"]) == 10

    def test_inline_z_argument(self):
        assert mr.resolve_quantization_bits(["-v", "-Z8", "-d1"]) == 8

    def test_video_encoding_implies_eight_bits(self):
        assert mr.resolve_quantization_bits(["-v", "-E", "-d1"]) == 8

    def test_z_takes_precedence_over_e(self):
        assert mr.resolve_quantization_bits(["-Z", "12", "-E"]) == 12

    def test_no_quantization(self):
        assert mr.resolve_quantization_bits(["-v", "-d1"]) is None

    def test_separate_z_missing_value_returns_none(self):
        assert mr.resolve_quantization_bits(["-v", "-Z"]) is None

    def test_separate_z_non_integer_value_returns_none(self):
        assert mr.resolve_quantization_bits(["-Z", "high"]) is None


class TestQuantizeGray:
    def test_eight_bit_snaps_to_grid(self):
        # 50.0 in 0-100 -> round(0.5 * 255) = 128 -> 128/255*100 = 50.1961
        result = mr.quantize_gray([[50.0, 50.0, 50.0]], 8)
        assert result == [[50.1961, 50.1961, 50.1961]]

    def test_extremes_are_exact(self):
        result = mr.quantize_gray([[0.0, 0.0, 0.0], [100.0, 100.0, 100.0]], 8)
        assert result == [[0.0, 0.0, 0.0], [100.0, 100.0, 100.0]]

    def test_empty_gray(self):
        assert mr.quantize_gray([], 8) == []

    def test_does_not_mutate_input(self):
        gray = [[50.0, 50.0, 50.0]]
        mr.quantize_gray(gray, 8)
        assert gray == [[50.0, 50.0, 50.0]]


class TestReportTrcLabel:
    def test_default_target_is_bt1886(self):
        assert mr.report_trc_label(2.4, "B", 0) == "BT.1886"

    def test_non_default_gamma_unlabelled(self):
        assert mr.report_trc_label(2.2, "B", 0) == ""

    def test_non_default_type_unlabelled(self):
        assert mr.report_trc_label(2.4, "b", 0) == ""

    def test_output_offset_unlabelled(self):
        assert mr.report_trc_label(2.4, "B", 0.5) == ""
