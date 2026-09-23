# EntroPy - Forensic Entropy & Randomness Analyzer

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Framework](https://img.shields.io/badge/GUI-PySide6%20%2F%20Qt6-green.svg)
![Graphics Engine](https://img.shields.io/badge/Plotting-PyQtGraph-orange.svg)
![License](https://img.shields.io/badge/license-MIT-brightgreen.svg)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)

**EntroPy** is a high-performance, cross-platform forensic tool engineered for deep entropy analysis, byte distribution profiling, and structural randomness detection in binary files. It leverages memory-mapped file processing, vectorized NumPy operations, and GPU-accelerated Qt graphing to deliver real-time sliding-window visualizations for files of arbitrary size without overloading system memory.

---

## Key Features

* **Memory-Mapped Vectorized Processing:** Employs `mmap` combined with NumPy stride tricks to slice and analyze multi-gigabyte binaries efficiently in non-blocking batches.
* **Normalized Statistical Engine:**
  * **Shannon Entropy ($H$):** Measures global and local information density ($0.0 \text{ to } 8.0 \text{ bits/byte}$).
  * **Cramér's V ($V$):** Evaluates non-uniformity as a size-independent normalized metric ($0.0 \text{ to } 1.0$).
  * **Lag-1 Serial Correlation ($r_1$):** Detects contiguity dependencies and pattern repetition between adjacent bytes.
  * **Arithmetic Mean ($\bar{x}$):** Assesses global distribution bias relative to uniform theoretical randomness ($\bar{x} = 127.5$).
* **Stream Corruption & Zero-Filling Detection:** Automatically identifies localized entropy drops and anomalous padding blocks within compressed/encrypted data streams (e.g., damaged WebM, MKV, or ZIP archives).
* **Magic Bytes Header Recognition:** Auto-detects standard binary signatures (Matroska/WebM, PE, ELF, ZIP, PNG, JPEG, PDF, ZSTD, 7z) upon loading.
* **Synchronized 512-Byte Region Highlight:** Clicking anywhere on the time-series plot projects a semi-transparent $512\text{-byte}$ region highlight on the graph that locks directly to the real-time Hexadecimal/ASCII inspection pane.
* **Asynchronous Execution Architecture:** Multi-threaded worker queue (`QThread`) providing continuous percentage updates via a UI progress overlay frame during initial file intake.
* **Modern High-DPI Desktop Interface:** Drag-and-drop file loading, zoom boundary protection, card-style metric rows with inline sub-descriptions, and one-click clipboard copy functionality.

---

## Graphical User Interface Overview

```text
+-----------------------------------------------------------------------------------+
|  [Open File]  [ ⇩ Drag & Drop File Here ]  file_sample.bin                        |
|  -------------------------------------------------------------------------------  |
|  File Size: 76,814,337 bytes (73.26 MB) | Magic Bytes: 1A 45 DF A3... | WebM/MKV  |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  SLIDING WINDOW PLOT (PyQtGraph)                                                  |
|  - Shannon Entropy Curve (Green + 15% Translucent Fill)                           |
|  - Null-Byte Ratio Overlay (Orange Dashed Line)                                   |
|  - 512-Byte Region Highlight Box (Cyan Semi-Transparent)                          |
|                                                                                   |
+--------------------------------------------------+--------------------------------+
| GLOBAL METRICS & TREND                           | REAL-TIME OFFSET INSPECTION    |
| - MD5 / SHA-256 Hashes (One-click copy)          | 512-Byte Monospace Hex Dump    |
| - Shannon Entropy H(X) & Cramér's V (V)          | Formatted Hex & ASCII Views    |
| - Arithmetic Mean & Serial Correlation           | Offset Line Marker Pointer (>) |
| - Probabilities & Red Critical Anomaly Rationale | Synchronized to Plot Clicks    |
+--------------------------------------------------+--------------------------------+
```

---

## Mathematical Foundations

### 1. Shannon Entropy
Measures the average information content or unpredictability per byte in a discrete probability distribution:

$$H(X) = -\sum_{i=0}^{255} P(x_i) \log_2 P(x_i)$$

* **$H(X) \approx 0.0$:** Highly repetitive or uniform stream (e.g., zero-padded memory dumps).
* **$H(X) \approx 8.0$:** Maximum entropy, indicating compressed, encrypted, or purely random data.

### 2. Cramér's V (Normalized Non-Uniformity Index)
While standard Chi-Square ($\chi^2$) metrics scale linearly with file size $N$ (yielding values in the millions for large binaries), **Cramér's V** normalizes the deviation independently of file length:

$$V = \sqrt{\frac{\chi^2}{255 \cdot N}}$$

| Cramér's V Value | Statistical Interpretation | Common File Types |
| :--- | :--- | :--- |
| **$V \le 0.005$ ($0.5\%$)** | High Uniformity / Randomness | Encrypted volumes, `/dev/urandom`, AES streams |
| **$0.005 < V \le 0.05$ ($0.5\% - 5.0\%$)** | Low Deviation | Compressed containers (ZIP, WebM, PNG, ZSTD) |
| **$0.05 < V \le 0.30$ ($5.0\% - 30.0\%$)** | Moderate Deviation | Executables (PE, ELF), compiled code, databases |
| **$V > 0.30$ ($> 30.0\%$)** | High Non-Uniformity | Plain text, zero-padded streams, corrupted data |

### 3. Lag-1 Serial Correlation
Measures linear dependency between adjacent byte pairs $(x_i, x_{i+1})$ across the binary file:

$$r_1 = \frac{\sum_{i=1}^{N-1} (x_i - \bar{x})(x_{i+1} - \bar{x})}{\sum_{i=1}^{N} (x_i - \bar{x})^2}$$

* **$r_1 \approx 0.0$:** Uncorrelated byte sequences.
* **$r_1 > 0.1$:** Residual pattern structure typical of uncompressed or partially corrupted streams.

---

## Installation & Requirements

### System Prerequisites
* **Operating System:** macOS 11+, Linux (Ubuntu/Debian/Fedora/Arch), or Windows 10/11.
* **Python Runtime:** Python `3.10` or higher.

### Step-by-Step Environment Setup

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/cuarentaysiete/entroPy.git
   cd entroPy
   ```

2. **Create and Activate a Dedicated Virtual Environment:**
   ```bash
   python3 -m venv entropy_env
   source entropy_env/bin/activate
   ```
   *(On Windows, activate using `entropy_env\Scripts\activate`)*

3. **Install Required Dependencies:**
   ```bash
   pip install numpy PySide6 pyqtgraph
   ```

---

## Usage Guide

### Launching the Application

Run `gui.py` from your activated virtual environment:

```bash
python gui.py
```

### Analyzing Files
1. **Intake:** Click the **Open File** button or drag and drop any file directly onto the interface.
2. **Progress:** Monitor the real-time percentage progress bar on the overlay pane during calculations.
3. **Graph Interaction:**
   * **Left-Click:** Select any offset on the time-series plot to display the corresponding $512\text{-byte}$ region highlight on the graph and view the aligned hexadecimal dump below.
   * **Right-Click Drag / Scroll Wheel:** Zoom into localized offset regions. Zoom out is bounded to prevent view displacement beyond valid memory offsets ($0.0 \text{ to } 8.2$).
4. **Copying Metrics:** Click the **Copy** button alongside any cryptographic hash or global statistical parameter to store the precise value in your clipboard.

---

## Repository Structure

```text
entroPy/
├── core.py         # Computational statistics engine, memory-mapping & heuristic classification
├── gui.py          # PySide6 desktop interface, PyQtGraph views & interactive event logic
├── .gitignore      # Exclusion rules for virtual environments, system files & test datasets
├── LICENSE         # MIT License declaration
└── README.md       # Project documentation
```

---

## License

Distributed under the **MIT License**. See `LICENSE` for complete licensing terms and copyright details.