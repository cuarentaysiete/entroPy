# EntroPy - Forensic Entropy & Randomness Analyzer

**EntroPy** is a high-performance, cross-platform forensic tool designed to analyze information density, byte distribution, and statistical randomness in binary files. Built with Python, NumPy, PySide6 (Qt6), and PyQtGraph, it combines memory-mapped data ingestion with vectorized statistical processing to deliver real-time sliding-window entropy visualizations and offset-level inspection.

---

## Key Features

* **Vectorized Sliding-Window Analysis:** Computes localized Shannon Entropy $H(X)$ and null-byte ratios over memory-mapped binaries using optimized NumPy stride tricks.
* **Granular Statistical Framework:**
  * **Shannon Entropy ($H$):** Measures global information density ($0.0 \text{ to } 8.0 \text{ bits/byte}$).
  * **Cramér's V ($V$):** Normalized non-uniformity index ($0.0 \text{ to } 1.0$), scaling independently of total file size.
  * **Serial Correlation ($r_1$):** Detects lag-1 contiguity dependencies between adjacent bytes.
  * **Arithmetic Mean ($\bar{x}$):** Evaluates central distribution tendency against the theoretical uniform mean ($127.5$).
* **Stream Corruption & Anomaly Detection:** Automatically flags localized entropy drops and zero-filling patterns in high-entropy streams (e.g., damaged video/audio media files).
* **Magic Bytes Format Recognition:** Parses file headers to identify standard compressed archives, executable containers, and media streams.
* **Interactive Offset Inspection:** Click anywhere on the time-series plot to highlight the exact 512-byte aligned region and inspect its synchronized Hexadecimal / ASCII dump.
* **Non-Blocking Architecture:** Fully decoupled execution engine using background worker threads (`QThread`) with percentage progress overlay.
* **Modern High-DPI UI:** High-readability typography, drag-and-drop file loading, strict zoom boundary limits, and one-click clipboard copy functionality for all hashes and metrics.

---

## Technical Stack

* **Language:** Python 3.10+
* **Core Engine:** NumPy (vectorized array operations), `mmap` (memory-mapped file ingestion)
* **Graphical Interface:** PySide6 (Qt6 GUI toolkit)
* **Plotting Engine:** PyQtGraph (OpenGL/Qt accelerated graphics)

---

## Mathematical Framework

### Shannon Entropy
$$H(X) = -\sum_{i=0}^{255} P(x_i) \log_2 P(x_i)$$

### Cramér's V (Normalized Goodness-of-Fit)
$$V = \sqrt{\frac{\chi^2}{255 \cdot N}}$$
Where $N$ represents the total byte count and $\chi^2$ measures goodness-of-fit against a uniform distribution.

### Lag-1 Serial Correlation
$$r_1 = \frac{\sum_{i=1}^{N-1} (x_i - \bar{x})(x_{i+1} - \bar{x})}{\sum_{i=1}^{N} (x_i - \bar{x})^2}$$

---

## Installation & Setup

### Prerequisites

Ensure Python 3.10 or higher is installed on your system (macOS / Linux / UNIX / Windows).

### Environment Setup

1. Clone the repository:
   ```bash
   git clone [https://github.com/cuarentaysiete/entroPy.git](https://github.com/cuarentaysiete/entroPy.git)
   cd entroPy