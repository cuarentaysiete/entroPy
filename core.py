"""
EntroPy - Core Analysis Engine
Provides fast, statistically rigorous entropy and randomness analysis
for binary files using memory mapping and vectorized NumPy operations.
Includes stream anomaly/corruption detection, magic bytes signature parsing,
Cramer's V normalized uniformity index, and granular progress callbacks.
"""

from dataclasses import dataclass
import hashlib
import math
import mmap
import os
from typing import List, Optional, Callable
import numpy as np


@dataclass
class FileMetadata:
    """Holds physical file parameters, cryptographic hashes, and parsed file format."""
    file_path: str
    file_size: int
    magic_bytes: bytes
    detected_format: str
    md5: str
    sha1: str
    sha256: str


@dataclass
class GlobalMetrics:
    """Holds statistical randomness parameters for the entire file."""
    shannon_entropy: float
    cramers_v: float
    cramers_v_estimate: str
    arithmetic_mean: float
    serial_correlation: float
    null_byte_ratio: float


@dataclass
class WindowAnalysisResult:
    """Holds windowed time-series analysis data for plotting."""
    block_offsets: np.ndarray
    entropy_series: np.ndarray
    null_ratio_series: np.ndarray
    block_size: int
    stride: int


@dataclass
class TrendEstimation:
    """Holds probabilistic estimation of data nature and rationale."""
    prob_compressed: float
    prob_encrypted: float
    prob_structured: float
    prob_padding: float
    prob_corrupted: float
    dominant_category: str
    rationale: List[str]


@dataclass
class AnalysisReport:
    """Master container for complete file analysis."""
    metadata: FileMetadata
    global_metrics: GlobalMetrics
    windowed_analysis: WindowAnalysisResult
    trend: TrendEstimation


def identify_file_format(magic: bytes) -> str:
    """Identifies human-readable file format based on magic bytes signatures."""
    if magic.startswith(b"\x1a\x45\xdf\xa3"):
        return "WebM / Matroska Video (MKV)"
    if magic.startswith(b"PK\x03\x04"):
        return "ZIP Archive / OpenXML Document"
    if magic.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG Image"
    if magic.startswith(b"\xff\xd8\xff"):
        return "JPEG Image"
    if magic.startswith(b"GIF87a") or magic.startswith(b"GIF89a"):
        return "GIF Image"
    if magic.startswith(b"RIFF") and len(magic) >= 12 and magic[8:12] == b"WEBP":
        return "WebP Image"
    if magic.startswith(b"%PDF"):
        return "PDF Document"
    if magic.startswith(b"\x1f\x8b"):
        return "GZIP Compressed Archive"
    if magic.startswith(b"BZh"):
        return "BZIP2 Compressed Archive"
    if magic.startswith(b"\xfd7zXZ\x00"):
        return "XZ Compressed Archive"
    if magic.startswith(b"\x28\xb5\x2f\xfd"):
        return "Zstandard (ZSTD) Compressed"
    if magic.startswith(b"7z\xbc\xaf\x27\x1c"):
        return "7-Zip Archive"
    if magic.startswith(b"MZ"):
        return "Windows PE Executable (.exe/.dll)"
    if magic.startswith(b"\x7fELF"):
        return "Linux ELF Executable"
    if len(magic) >= 8 and magic[4:8] in (b"ftyp", b"moov"):
        return "MP4 / ISOBMFF Media Container"
    return "Unknown / Raw Binary Format"


def compute_file_metadata(
    file_path: str,
    chunk_size: int = 262144,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> FileMetadata:
    """Computes cryptographic hashes with granular progress reporting."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    file_size = os.path.getsize(file_path)
    if file_size == 0:
        raise ValueError("Cannot analyze an empty file (0 bytes).")

    md5_hash = hashlib.md5()
    sha1_hash = hashlib.sha1()
    sha256_hash = hashlib.sha256()

    bytes_processed = 0
    last_pct = -1

    with open(file_path, "rb") as f:
        magic_bytes = f.read(16)
        f.seek(0)

        while chunk := f.read(chunk_size):
            md5_hash.update(chunk)
            sha1_hash.update(chunk)
            sha256_hash.update(chunk)
            
            bytes_processed += len(chunk)
            if progress_callback and file_size > 0:
                pct = int((bytes_processed / file_size) * 40)
                if pct != last_pct:
                    mb_read = bytes_processed / (1024 * 1024)
                    mb_total = file_size / (1024 * 1024)
                    progress_callback(pct, f"Computing cryptographic hashes ({mb_read:.1f} / {mb_total:.1f} MB)...")
                    last_pct = pct

    detected_format = identify_file_format(magic_bytes)

    return FileMetadata(
        file_path=os.path.abspath(file_path),
        file_size=file_size,
        magic_bytes=magic_bytes,
        detected_format=detected_format,
        md5=md5_hash.hexdigest(),
        sha1=sha1_hash.hexdigest(),
        sha256=sha256_hash.hexdigest()
    )


def compute_global_statistics(
    buffer: mmap.mmap,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> GlobalMetrics:
    """Computes Shannon entropy, Cramer's V, mean, null ratio, and serial correlation."""
    if progress_callback:
        progress_callback(45, "Calculating global byte distribution...")

    n_bytes = len(buffer)
    data = np.frombuffer(buffer, dtype=np.uint8)

    counts = np.bincount(data, minlength=256)
    probabilities = counts / n_bytes

    non_zero_probs = probabilities[probabilities > 0]
    shannon_entropy = float(-np.sum(non_zero_probs * np.log2(non_zero_probs)))

    # Cramér's V calculation: V = sqrt(chi2 / (N * (k - 1)))
    expected_count = n_bytes / 256.0
    chi_square = float(np.sum((counts - expected_count) ** 2 / expected_count))
    cramers_v = math.sqrt(chi_square / (255.0 * n_bytes)) if n_bytes > 0 else 0.0

    if cramers_v <= 0.005:
        v_est = "High uniformity / Random or Encrypted (0.0% - 0.5%)"
    elif cramers_v <= 0.05:
        v_est = "Low deviation / Compressed Stream (0.5% - 5.0%)"
    elif cramers_v <= 0.30:
        v_est = "Moderate deviation / Structured Data (5.0% - 30.0%)"
    else:
        v_est = "High non-uniformity / Text, Padding or Corrupted (>30.0%)"

    arithmetic_mean = float(np.mean(data))
    null_byte_ratio = float(counts[0] / n_bytes)

    if progress_callback:
        progress_callback(55, "Calculating lag-1 serial correlation...")

    if n_bytes > 1:
        x = data[:-1].astype(np.float64)
        y = data[1:].astype(np.float64)
        mean_x = np.mean(x)
        mean_y = np.mean(y)
        var_x = np.sum((x - mean_x) ** 2)
        var_y = np.sum((y - mean_y) ** 2)
        cov = np.sum((x - mean_x) * (y - mean_y))
        
        denom = math.sqrt(var_x * var_y)
        serial_correlation = float(cov / denom) if denom != 0 else 0.0
    else:
        serial_correlation = 0.0

    return GlobalMetrics(
        shannon_entropy=shannon_entropy,
        cramers_v=cramers_v,
        cramers_v_estimate=v_est,
        arithmetic_mean=arithmetic_mean,
        serial_correlation=serial_correlation,
        null_byte_ratio=null_byte_ratio
    )


def compute_windowed_analysis(
    buffer: mmap.mmap,
    block_size: int = 0,
    stride: int = 0,
    target_points: int = 4000,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> WindowAnalysisResult:
    """Computes windowed entropy time-series in chunked batches with smooth progress reporting."""
    file_size = len(buffer)

    if block_size <= 0:
        block_size = max(1280, min(65536, file_size // 100)) if file_size > 1280 else file_size

    if stride <= 0:
        calculated_stride = file_size // target_points if file_size > target_points else block_size
        stride = max(256, calculated_stride)

    data = np.frombuffer(buffer, dtype=np.uint8)
    
    if file_size < block_size:
        block_size = file_size
        num_blocks = 1
        stride = file_size
    else:
        num_blocks = (file_size - block_size) // stride + 1

    offsets = np.arange(num_blocks, dtype=np.int64) * stride
    entropy_series = np.zeros(num_blocks, dtype=np.float32)
    null_ratio_series = np.zeros(num_blocks, dtype=np.float32)

    batch_size = 1000
    last_pct = -1

    for start_idx in range(0, num_blocks, batch_size):
        end_idx = min(start_idx + batch_size, num_blocks)
        
        sub_shape = (end_idx - start_idx, block_size)
        sub_strides = (data.strides[0] * stride, data.strides[0])
        blocks_view = np.lib.stride_tricks.as_strided(data[start_idx * stride:], shape=sub_shape, strides=sub_strides)

        counts = np.array([(blocks_view == i).sum(axis=1) for i in range(256)], dtype=np.float32)
        probs = counts / block_size

        with np.errstate(divide='ignore', invalid='ignore'):
            log_probs = np.where(probs > 0, np.log2(probs), 0)
            entropy_series[start_idx:end_idx] = -np.sum(probs * log_probs, axis=0)

        null_ratio_series[start_idx:end_idx] = counts[0] / block_size

        if progress_callback:
            pct = int(60 + (end_idx / num_blocks) * 35)
            if pct != last_pct:
                progress_callback(pct, f"Analyzing sliding windows ({end_idx:,} / {num_blocks:,} blocks)...")
                last_pct = pct

    return WindowAnalysisResult(
        block_offsets=offsets,
        entropy_series=entropy_series,
        null_ratio_series=null_ratio_series,
        block_size=block_size,
        stride=stride
    )


def evaluate_trend(
    metrics: GlobalMetrics,
    magic_bytes: bytes,
    window_result: WindowAnalysisResult
) -> TrendEstimation:
    """Evaluates statistical trends and detects stream corruption / zero-filling anomalies."""
    rationale = []
    
    p_compressed = 0.0
    p_encrypted = 0.0
    p_structured = 0.0
    p_padding = 0.0
    p_corrupted = 0.0

    entropy = metrics.shannon_entropy
    r1 = abs(metrics.serial_correlation)
    null_ratio = metrics.null_byte_ratio
    v_val = metrics.cramers_v

    total_blocks = len(window_result.entropy_series)
    max_block_entropy = float(np.max(window_result.entropy_series)) if total_blocks > 0 else 0.0
    
    anomalous_blocks = np.sum((window_result.null_ratio_series > 0.25) | (window_result.entropy_series < 3.0))
    anomaly_ratio = float(anomalous_blocks / total_blocks) if total_blocks > 0 else 0.0

    if anomaly_ratio > 0.02 and max_block_entropy > 6.0:
        p_corrupted += min(95.0, anomaly_ratio * 250.0 + 40.0)
        rationale.append(
            f"CRITICAL ANOMALY: {anomaly_ratio:.1%} of analyzed blocks exhibit severe entropy drops or null-padding "
            f"within a high-entropy stream. Strong indication of file corruption, truncation, or zero-filling."
        )

    if null_ratio > 0.60 or entropy < 2.0:
        p_padding += 80.0
        rationale.append(f"High concentration of null bytes ({null_ratio:.1%}) or low global entropy ({entropy:.2f}).")

    if 2.0 <= entropy < 7.2:
        p_structured += 70.0
        rationale.append(f"Global entropy ({entropy:.2f} bits/byte) aligns with uncompressed structured data or text.")
    elif 7.2 <= entropy < 7.85:
        p_structured += 30.0
        p_compressed += 40.0
        rationale.append(f"Moderate-to-high entropy ({entropy:.2f} bits/byte) indicates partial compression or structured streams.")

    if entropy >= 7.85:
        if r1 < 0.002 and v_val < 0.008:
            p_encrypted += 60.0
            p_compressed += 30.0
            rationale.append(f"Near-zero serial correlation ({r1:.5f}) and minimal Cramer's V ({v_val:.5f}) indicate high uniformity (Encrypted/Random).")
        else:
            p_compressed += 60.0
            p_encrypted += 20.0
            rationale.append(f"Residual serial correlation ({r1:.5f}) or Cramer's V deviation ({v_val:.5f}) indicates stream compression.")

    known_compressed_headers = [b"PK\x03\x04", b"\x1f\x8b", b"\x42\x5a", b"\xfd7zXZ", b"\x28\xb5\x2f\xfd", b"\x1a\x45\xdf\xa3"]
    if any(magic_bytes.startswith(hdr) for hdr in known_compressed_headers):
        p_compressed += 20.0
        p_encrypted = max(0.0, p_encrypted - 15.0)
        rationale.append("Recognized media container or compressed archive signature at header.")

    total_raw = p_compressed + p_encrypted + p_structured + p_padding + p_corrupted
    if total_raw > 0:
        p_compressed = round((p_compressed / total_raw) * 100, 1)
        p_encrypted = round((p_encrypted / total_raw) * 100, 1)
        p_structured = round((p_structured / total_raw) * 100, 1)
        p_padding = round((p_padding / total_raw) * 100, 1)
        p_corrupted = round((p_corrupted / total_raw) * 100, 1)
    else:
        p_structured = 100.0

    cat_map = {
        "Corrupted / Zero-Padded Stream": p_corrupted,
        "Compressed Data": p_compressed,
        "Encrypted / Random Data": p_encrypted,
        "Structured / Executable / Text": p_structured,
        "Padding / Flat Data": p_padding
    }
    dominant_category = max(cat_map, key=cat_map.get)

    return TrendEstimation(
        prob_compressed=p_compressed,
        prob_encrypted=p_encrypted,
        prob_structured=p_structured,
        prob_padding=p_padding,
        prob_corrupted=p_corrupted,
        dominant_category=dominant_category,
        rationale=rationale
    )


def analyze_file(
    file_path: str,
    block_size: int = 0,
    stride: int = 0,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> AnalysisReport:
    """Main entry point for running a complete analysis on a file."""
    metadata = compute_file_metadata(file_path, progress_callback=progress_callback)

    with open(file_path, "rb") as f:
        with mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ) as mm:
            global_metrics = compute_global_statistics(mm, progress_callback=progress_callback)
            window_result = compute_windowed_analysis(mm, block_size=block_size, stride=stride, progress_callback=progress_callback)
            trend = evaluate_trend(global_metrics, metadata.magic_bytes, window_result)

    if progress_callback:
        progress_callback(100, "Analysis complete.")

    return AnalysisReport(
        metadata=metadata,
        global_metrics=global_metrics,
        windowed_analysis=window_result,
        trend=trend
    )