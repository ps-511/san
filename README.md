# SAN Cache Replacement Policy Simulator (Enterprise Edition)

An interactive, enterprise-grade simulation, benchmarking, and visualization laboratory for Storage Area Network (SAN) cache replacement policies built with **Python**, **Streamlit**, and **Matplotlib**.

---

## 1. What's New in the Enterprise Edition

This simulator goes beyond basic text tables to provide a realistic model of enterprise SAN storage controller caching:

- **Hardware Latency Modeling:** 
  - Simulates controller NVRAM/DRAM cache hit latency (`0.1 ms`) vs backend disk/array miss latency (`10.0 ms`).
  - Automatically computes **Effective Access Time (EAT)**, total I/O duration, latency saved, and overall I/O speedup factor ($X\times$ faster than uncached disk).
- **Synthetic SAN Workload Generators:**
  - **OLTP Database (Zipfian 80/20):** Models transactional databases where ~80% of I/O operations target ~20% of hot blocks.
  - **Sequential Streaming Scan (Backup/Media):** Models backup sweeps and video streaming that cycle sequentially through LUN blocks.
  - **Cache Thrashing (Capacity + 1):** Models memory thrashing where the working set size exceeds cache capacity.
  - **Uniform Random Access:** Models random un-cached storage accesses across wide address spaces.
  - **Custom String:** Accepts user-defined block sequences (e.g. `A, B, C, A, D, B, E`).
- **Interactive Cache Frame Memory Slot Grid:**
  - Visually renders physical cache slots (Slot #1, Slot #2, Slot #3...) showing resident block tags, hit counts, arrival timestamps, and live HIT/MISS/COLD highlight badges.
- **Time-Travel Step Scrubber:**
  - An interactive step slider to scrub back and forth across request steps ($t = 1 \dots N$).
  - Displays the exact architectural justification for every placement or eviction decision (including FIFO tie-breakers for LFU).
- **Multi-Chart Analytics Suite (Matplotlib):**
  - **Bar Charts:** Cache Hits vs. Misses across algorithms.
  - **Hit Ratio Comparison (%):** Benchmarked side-by-side.
  - **Cumulative Hit Ratio Convergence Curve:** Time-series line chart tracking how cache hit rates evolve and stabilize over time.
  - **Effective Access Time & Total Latency:** Visualizes storage duration vs. an uncached storage baseline.
- **CSV Data Export:**
  - One-click export of complete step-by-step simulation logs for offline auditing and reporting.

---

## 2. Directory Structure

```text
san_cache_simulator/
│
├── algorithms.py       # Core FIFO, LRU, LFU algorithms, latency modeling & workload generators
├── app.py              # Streamlit dashboard, hardware slot visualizer & Matplotlib analytics
├── requirements.txt    # Required Python libraries
└── README.md           # Documentation, architectural guide & user manual
```

---

## 3. Supported Cache Replacement Policies

### 1. FIFO (First In First Out)
- **Principle:** Evicts the storage block that entered the cache earliest.
- **Behavior:** Treats cache memory as a FIFO queue. Cache hits do not alter arrival order.
- **SAN Characteristic:** Simple to implement in hardware controllers, but vulnerable to **Belady's Anomaly** (increasing cache frames can counter-intuitively increase misses).

### 2. LRU (Least Recently Used)
- **Principle:** Evicts the storage block that has not been accessed for the longest duration.
- **Behavior:** Maintains recency ordering. On a hit or insert, the block moves to the Most Recently Used (MRU) position; evictions remove from the Least Recently Used (LRU) head.
- **SAN Characteristic:** Highly effective for workloads with strong **Temporal Locality** (such as database index pages). Vulnerable to cache pollution during long sequential scans.

### 3. LFU (Least Frequently Used with FIFO Tie-Breaking)
- **Principle:** Evicts the storage block with the lowest access frequency.
- **Behavior:** Increments an access counter on each cache hit. When an eviction is needed, blocks with minimum frequency are identified. If there is a tie, the block that arrived earliest (**FIFO tie-breaker**) is evicted.
- **SAN Characteristic:** Capitalizes on **Frequency Locality**. Without aging mechanisms, historically hot blocks can monopolize cache slots.

---

## 4. Hardware Latency Formulas

$$\text{Effective Access Time (EAT)} = (\text{Hit Ratio} \times \text{Hit Latency}) + (\text{Miss Ratio} \times \text{Miss Latency})$$

$$\text{Total Time With Cache} = (\text{Hits} \times \text{Hit Latency}) + (\text{Misses} \times \text{Miss Latency})$$

$$\text{Total Time Without Cache} = \text{Total Requests} \times \text{Miss Latency}$$

$$\text{Latency Speedup} = \frac{\text{Total Time Without Cache}}{\text{Total Time With Cache}}$$

---

## 5. Installation & Setup

### Prerequisites
- Python 3.8+ installed.

### Step 1: Open Terminal / PowerShell
Navigate into the project folder:

```bash
cd san_cache_simulator
```

### Step 2: (Optional) Activate Virtual Environment
- **Windows (PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  ```
- **macOS / Linux:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 6. Running the Simulator

Launch the dashboard:

```bash
streamlit run app.py
```

The application will launch in your web browser at `http://localhost:8501`.

---

## 7. Expected Demonstration Walkthrough

### Test Case:
- **Request Sequence:** `A, B, C, A, D, B, E`
- **Cache Capacity:** `3 Blocks`
- **Hit Latency:** `0.1 ms` | **Miss Latency:** `10.0 ms`

### Step-by-Step Evolution:

#### FIFO Policy
| Step | Block | Status | Evicted | Cache Slots | Eviction Rationale |
|:---:|:---:|:---:|:---:|:---:|:---|
| 1 | A | MISS | - | `[ A ]` | Cold miss: allocated free slot. |
| 2 | B | MISS | - | `[ A, B ]` | Cold miss: allocated free slot. |
| 3 | C | MISS | - | `[ A, B, C ]` | Cold miss: allocated free slot. |
| 4 | A | **HIT** | - | `[ A, B, C ]` | Hit in cache; arrival order preserved. |
| 5 | D | MISS | A | `[ B, C, D ]` | Cache full: evicted oldest block `A` (entered at Step 1). |
| 6 | B | **HIT** | - | `[ B, C, D ]` | Hit in cache; arrival order preserved. |
| 7 | E | MISS | B | `[ C, D, E ]` | Cache full: evicted oldest block `B` (entered at Step 2). |

- **Hits:** 2 | **Misses:** 5 | **Evictions:** 2
- **Hit Ratio:** `28.57%` | **Miss Ratio:** `71.43%`
- **Effective Access Time (EAT):** `7.17 ms` (Uncached: `10.0 ms`)
- **Total Latency:** `50.2 ms` vs `70.0 ms` uncached (**1.39x Speedup**)

---

#### LRU Policy
| Step | Block | Status | Evicted | Cache Slots (LRU → MRU) | Eviction Rationale |
|:---:|:---:|:---:|:---:|:---:|:---|
| 1 | A | MISS | - | `[ A ]` | Cold miss: allocated free slot. |
| 2 | B | MISS | - | `[ A, B ]` | Cold miss: allocated free slot. |
| 3 | C | MISS | - | `[ A, B, C ]` | Cold miss: allocated free slot. |
| 4 | A | **HIT** | - | `[ B, C, A ]` | Hit: `A` promoted to MRU position. |
| 5 | D | MISS | B | `[ C, A, D ]` | Evicted least recently accessed block `B` (last used at Step 2). |
| 6 | B | MISS | C | `[ A, D, B ]` | Evicted least recently accessed block `C` (last used at Step 3). |
| 7 | E | MISS | A | `[ D, B, E ]` | Evicted least recently accessed block `A` (last used at Step 4). |

- **Hits:** 1 | **Misses:** 6 | **Evictions:** 3
- **Hit Ratio:** `14.29%` | **Miss Ratio:** `85.71%`
- **Effective Access Time (EAT):** `8.59 ms`

---

#### LFU Policy (FIFO Tie-Breaker)
| Step | Block | Status | Evicted | Frequencies & Tie-Breaking | Cache Slots |
|:---:|:---:|:---:|:---:|:---|:---:|
| 1 | A | MISS | - | `{A: 1}` | `[ A ]` |
| 2 | B | MISS | - | `{A: 1, B: 1}` | `[ A, B ]` |
| 3 | C | MISS | - | `{A: 1, B: 1, C: 1}` | `[ A, B, C ]` |
| 4 | A | **HIT** | - | `{A: 2, B: 1, C: 1}` (Incremented `A`) | `[ A, B, C ]` |
| 5 | D | MISS | B | Lowest freq = 1 (B, C). `B` arrived before `C` → Evicted `B`. | `[ A, C, D ]` |
| 6 | B | MISS | C | Lowest freq = 1 (C, D). `C` arrived before `D` → Evicted `C`. | `[ A, D, B ]` |
| 7 | E | MISS | D | Lowest freq = 1 (D, B). `D` arrived before `B` → Evicted `D`. | `[ A, B, E ]` |

- **Hits:** 1 | **Misses:** 6 | **Evictions:** 3
- **Hit Ratio:** `14.29%` | **Miss Ratio:** `85.71%`
- **Effective Access Time (EAT):** `8.59 ms`
