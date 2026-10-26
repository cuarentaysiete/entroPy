"""Unit tests for the EntroPy core analysis engine (no GUI required)."""
import hashlib
import json
import mmap
import tempfile

import numpy as np
import pytest

import core


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mmap(data: bytes) -> mmap.mmap:
    """Memory-maps `data` into a temporary file and returns the mapping."""
    handle = tempfile.NamedTemporaryFile()
    handle.write(data)
    handle.flush()
    return mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)


def uniform_bytes(n: int = 1_000_000, seed: int = 42) -> bytes:
    """Bytes drawn from a flat 256-symbol distribution (MT19937, deterministic)."""
    return np.random.RandomState(seed).randint(0, 256, n, dtype=np.uint8).tobytes()


# ---------------------------------------------------------------------------
# Magic byte identification
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("magic,expected", [
    (b"\x1a\x45\xdf\xa3", "WebM / Matroska Video (MKV)"),
    (b"PK\x03\x04\x14\x00", "ZIP Archive / OpenXML Document"),
    (b"\x89PNG\r\n\x1a\n", "PNG Image"),
    (b"\xff\xd8\xff\xe0", "JPEG Image"),
    (b"GIF89a", "GIF Image"),
    (b"RIFF\x00\x00\x00\x00WEBP", "WebP Image"),
    (b"%PDF-1.7", "PDF Document"),
    (b"\x1f\x8b\x08\x00", "GZIP Compressed Archive"),
    (b"BZh91AY&", "BZIP2 Compressed Archive"),
    (b"\xfd7zXZ\x00", "XZ Compressed Archive"),
    (b"\x28\xb5\x2f\xfd", "Zstandard (ZSTD) Compressed"),
    (b"7z\xbc\xaf\x27\x1c", "7-Zip Archive"),
    (b"MZ\x90\x00", "Windows PE Executable (.exe/.dll)"),
    (b"\x7fELF\x02\x01", "Linux ELF Executable"),
    (b"\x00\x00\x00 ftypmp42", "MP4 / ISOBMFF Media Container"),
    (b"\x00\x01\x02\x03", "Unknown / Raw Binary Format"),
])
def test_identify_file_format(magic, expected):
    assert core.identify_file_format(magic) == expected


# ---------------------------------------------------------------------------
# File metadata / hashing
# ---------------------------------------------------------------------------

def test_metadata_hashes_known_values():
    handle = tempfile.NamedTemporaryFile()
    handle.write(b"abc")
    handle.flush()
    meta = core.compute_file_metadata(handle.name)
    assert meta.md5 == hashlib.md5(b"abc").hexdigest()
    assert meta.sha1 == hashlib.sha1(b"abc").hexdigest()
    assert meta.sha256 == hashlib.sha256(b"abc").hexdigest()
    assert meta.file_size == 3


def test_metadata_progress_callback_reaches_40():
    handle = tempfile.NamedTemporaryFile()
    handle.write(uniform_bytes(1_000_000))
    handle.flush()
    seen = []
    core.compute_file_metadata(handle.name, progress_callback=lambda p, m: seen.append(p))
    assert seen and max(seen) == 40


def test_metadata_empty_file_raises():
    handle = tempfile.NamedTemporaryFile()
    handle.write(b"")
    handle.flush()
    with pytest.raises(ValueError):
        core.compute_file_metadata(handle.name)


def test_metadata_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        core.compute_file_metadata("/nonexistent/path/to/file.bin")


# ---------------------------------------------------------------------------
# Global statistics
# ---------------------------------------------------------------------------

def test_global_statistics_exact_uniform_distribution():
    # Perfectly uniform: every byte value appears exactly 3906 times.
    data = bytes(np.tile(np.arange(256, dtype=np.uint8), 3906))
    g = core.compute_global_statistics(make_mmap(data))
    assert g.shannon_entropy == pytest.approx(8.0, abs=1e-9)
    assert g.cramers_v == pytest.approx(0.0, abs=1e-12)
    assert g.arithmetic_mean == pytest.approx(127.5, abs=1e-9)
    assert g.null_byte_ratio == pytest.approx(1 / 256, abs=1e-9)
    assert "High uniformity" in g.cramers_v_estimate


def test_global_statistics_random_distribution():
    g = core.compute_global_statistics(make_mmap(uniform_bytes()))
    assert g.shannon_entropy == pytest.approx(8.0, abs=1e-3)
    assert g.cramers_v < 0.005
    assert g.arithmetic_mean == pytest.approx(127.5, abs=2.0)
    assert abs(g.serial_correlation) < 0.01
    assert g.null_byte_ratio == pytest.approx(1 / 256, abs=0.01)


def test_global_statistics_all_zeros():
    g = core.compute_global_statistics(make_mmap(b"\x00" * 100_000))
    assert g.shannon_entropy == pytest.approx(0.0, abs=1e-9)
    assert g.null_byte_ratio == pytest.approx(1.0)
    assert g.arithmetic_mean == pytest.approx(0.0)
    # All mass on one symbol => chi2 ~= 255N => V ~= 1.0
    assert g.cramers_v == pytest.approx(1.0, abs=1e-6)
    assert g.serial_correlation == 0.0
    assert "High non-uniformity" in g.cramers_v_estimate


def test_serial_correlation_increasing_ramp():
    ramp = np.tile(np.arange(256, dtype=np.uint8), 64)
    assert core._compute_serial_correlation(ramp) > 0.95


def test_serial_correlation_random_near_zero():
    data = np.random.RandomState(1234).randint(0, 256, 1_000_000, dtype=np.uint8)
    assert abs(core._compute_serial_correlation(data)) < 0.01


def test_serial_correlation_single_byte():
    assert core._compute_serial_correlation(np.zeros(1, dtype=np.uint8)) == 0.0


def test_pair_correlation_alternating_pattern():
    # Alternating bytes: adjacent pairs anti-correlated, pairs at lag 2 aligned.
    data = bytes(bytearray([0x61, 0x62] * 50_000))
    g = core.compute_global_statistics(make_mmap(data))
    assert g.serial_correlation == pytest.approx(-1.0, abs=1e-6)
    assert g.pair_correlation == pytest.approx(1.0, abs=1e-6)


def test_pair_correlation_random_near_zero():
    data = np.random.RandomState(7).randint(0, 256, 1_000_000, dtype=np.uint8)
    assert abs(core._compute_serial_correlation(data, lag=2)) < 0.01


def test_pair_correlation_tiny_input():
    assert core._compute_serial_correlation(np.zeros(1, dtype=np.uint8), lag=2) == 0.0


def test_global_statistics_matches_naive_entropy():
    data = bytes(np.random.RandomState(9).randint(0, 256, 20_000, dtype=np.uint8))
    mm = make_mmap(data)
    counts = np.bincount(np.frombuffer(mm, dtype=np.uint8), minlength=256)
    p = counts / len(data)
    expected = -np.sum(p[p > 0] * np.log2(p[p > 0]))
    assert core.compute_global_statistics(mm).shannon_entropy == pytest.approx(expected, abs=1e-9)


# ---------------------------------------------------------------------------
# Windowed analysis
# ---------------------------------------------------------------------------

def test_windowed_uniform_blocks_all_near_max_entropy():
    w = core.compute_windowed_analysis(make_mmap(uniform_bytes()), block_size=4096, stride=4096)
    assert len(w.entropy_series) > 100
    assert w.entropy_series.min() > 7.5
    assert w.null_ratio_series.max() < 0.05


def test_windowed_zero_blocks():
    w = core.compute_windowed_analysis(make_mmap(b"\x00" * 100_000), block_size=4096, stride=4096)
    assert np.all(w.entropy_series < 1e-6)
    assert np.all(w.null_ratio_series > 1 - 1e-6)


def test_windowed_last_block_stays_within_bounds():
    # File size not a multiple of stride: no out-of-bounds reads, counts consistent.
    data = uniform_bytes(1_000_000)
    w = core.compute_windowed_analysis(make_mmap(data), block_size=4096, stride=4096)
    assert (w.block_offsets + w.block_size).max() <= len(data)


def test_windowed_tiny_files():
    for size in (1, 16, 100):
        w = core.compute_windowed_analysis(make_mmap(b"\xab" * size))
        assert len(w.entropy_series) == 1


def test_windowed_progress_range():
    seen = []
    core.compute_windowed_analysis(
        make_mmap(uniform_bytes(2_000_000)),
        block_size=4096, stride=4096,
        progress_callback=lambda p, m: seen.append(p),
    )
    assert 60 <= min(seen) and max(seen) <= 95


# ---------------------------------------------------------------------------
# Trend / heuristic classification
# ---------------------------------------------------------------------------

def _trend_for(data: bytes, magic: bytes = b"\x00\x01\x02\x03") -> core.TrendEstimation:
    mm = make_mmap(data)
    try:
        return core.evaluate_trend(
            core.compute_global_statistics(mm), magic, core.compute_windowed_analysis(mm)
        )
    finally:
        mm.close()


def test_trend_uniform_random_classified_encrypted():
    t = _trend_for(uniform_bytes(1_048_576, seed=1234))
    assert t.dominant_category == "Encrypted / Random Data"


def test_trend_all_zero_classified_padding():
    t = _trend_for(b"\x00" * 100_000)
    assert t.dominant_category == "Padding / Flat Data"
    assert t.prob_padding == max(t.prob_corrupted, t.prob_compressed, t.prob_encrypted, t.prob_structured, t.prob_padding)


def test_trend_zero_filled_inside_random_stream_classified_corrupted():
    data = bytearray(uniform_bytes(1_048_576, seed=555))
    n = len(data)
    data[int(n * 0.35):int(n * 0.65)] = b"\x00" * int(n * 0.3)
    t = _trend_for(bytes(data), magic=b"PK\x03\x04")
    assert t.dominant_category == "Corrupted / Zero-Padded Stream"
    assert any("CRITICAL ANOMALY" in r for r in t.rationale)


def test_trend_probabilities_sum_to_100():
    t = _trend_for(uniform_bytes(1_048_576, seed=1234))
    total = t.prob_corrupted + t.prob_compressed + t.prob_encrypted + t.prob_structured + t.prob_padding
    assert total == pytest.approx(100.0, abs=0.5)


def test_trend_low_entropy_text_classified_structured():
    text = (b"the quick brown fox jumps over the lazy dog. " * 2048)[:100_000]
    t = _trend_for(text)
    assert t.dominant_category == "Structured / Executable / Text"


# ---------------------------------------------------------------------------
# End-to-end analysis + JSON export
# ---------------------------------------------------------------------------

def test_analyze_file_end_to_end(tmp_path):
    path = tmp_path / "sample.bin"
    path.write_bytes(b"PK\x03\x04" + uniform_bytes(500_000, seed=77))
    seen = []
    report = core.analyze_file(str(path), progress_callback=lambda p, m: seen.append(p))

    assert report.metadata.detected_format == "ZIP Archive / OpenXML Document"
    assert report.metadata.file_size == path.stat().st_size
    assert 7.0 < report.global_metrics.shannon_entropy <= 8.0
    assert len(report.windowed_analysis.entropy_series) > 0
    assert report.trend.dominant_category
    assert seen[0] > 0 and seen[-1] == 100


def test_report_to_dict_is_json_serializable(tmp_path):
    path = tmp_path / "sample.bin"
    path.write_bytes(b"\x1a\x45\xdf\xa3" + uniform_bytes(50_000, seed=3))
    report = core.analyze_file(str(path))
    dumped = json.dumps(core.report_to_dict(report))
    assert "windowed_analysis" in dumped


def test_report_to_dict_converts_bytes_and_arrays(tmp_path):
    path = tmp_path / "sample.bin"
    path.write_bytes(b"PK\x03\x04" + b"\x00" * 1_000)
    d = core.report_to_dict(core.analyze_file(str(path)))
    assert isinstance(d["metadata"]["magic_bytes"], str)
    assert isinstance(d["windowed_analysis"]["entropy_series"], list)
    # "PK" header + 1000 zero bytes: nearly all nulls => very low window entropy
    assert d["windowed_analysis"]["entropy_series"][0] < 0.1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_prints_report(tmp_path, capsys):
    path = tmp_path / "sample.bin"
    path.write_bytes(b"PK\x03\x04" + uniform_bytes(200_000, seed=5))
    exit_code = core._cli([str(path)])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "ZIP Archive / OpenXML Document" in out
    assert "Shannon entropy" in out


def test_cli_json_output(tmp_path, capsys):
    path = tmp_path / "sample.bin"
    path.write_bytes(b"%PDF-1.7" + b"x" * 20_000)
    exit_code = core._cli([str(path), "--json"])
    payload = capsys.readouterr().out
    assert exit_code == 0
    data = json.loads(payload)
    assert data["metadata"]["detected_format"] == "PDF Document"


def test_cli_missing_file_returns_error(tmp_path, capsys):
    assert core._cli([str(tmp_path / "missing.bin")]) == 1
