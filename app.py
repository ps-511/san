"""
app.py
======
Enterprise-Grade SAN Cache Replacement Policy Simulator.
Interactive Streamlit Dashboard with Storage Latency Telemetry,
Live Cache Memory Slot Visualizer, Time-Travel Scrubber, and Analytics.
"""

import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
from typing import Dict, List

from algorithms import (
    parse_requests,
    generate_synthetic_workload,
    simulate_fifo,
    simulate_lru,
    simulate_lfu,
    simulate_all,
    SimulationResult
)

# ---------------------------------------------------------
# Page & Theme Configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="SAN Cache Simulator | Enterprise Storage Lab",
    page_icon="🗄️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Enterprise Storage CSS
st.markdown("""
<style>
    /* Metric Cards */
    .metric-container {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border-radius: 10px;
        padding: 16px 20px;
        color: #F8FAFC;
        border: 1px solid #334155;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .metric-title {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #94A3B8;
        margin-bottom: 6px;
    }
    .metric-val {
        font-size: 1.8rem;
        font-weight: 700;
        color: #38BDF8;
    }
    .metric-sub {
        font-size: 0.8rem;
        color: #CBD5E1;
        margin-top: 4px;
    }
    
    /* Cache Memory Slot Cards */
    .slot-card {
        border-radius: 8px;
        padding: 12px 14px;
        margin: 6px 4px;
        text-align: center;
        border: 1px solid #CBD5E1;
        background-color: #F8FAFC;
    }
    .slot-card-active-hit {
        background: #DCFCE7 !important;
        border: 2px solid #16A34A !important;
    }
    .slot-card-active-miss {
        background: #FEE2E2 !important;
        border: 2px solid #DC2626 !important;
    }
    .slot-header {
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        color: #64748B;
    }
    .slot-block {
        font-size: 1.5rem;
        font-weight: 800;
        color: #0F172A;
        margin: 4px 0;
    }
    .slot-meta {
        font-size: 0.75rem;
        color: #475569;
    }

    /* Status Badges */
    .badge-hit {
        background-color: #10B981;
        color: white;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 700;
    }
    .badge-miss {
        background-color: #EF4444;
        color: white;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------
# Sidebar: Workload & Hardware Configuration
# ---------------------------------------------------------
st.sidebar.title("🎛️ Controller Settings")

workload_category = st.sidebar.selectbox(
    "Workload Source:",
    [
        "Standard Sample (A, B, C, A, D, B, E)",
        "Custom Block String",
        "OLTP Database (Zipfian 80/20)",
        "Sequential Scan (Backup/Media)",
        "Thrashing Loop (Capacity + 1)",
        "Uniform Random Access"
    ]
)

# Workload Resolution
if workload_category == "Standard Sample (A, B, C, A, D, B, E)":
    raw_workload_string = "A, B, C, A, D, B, E"
    st.sidebar.info("Workload: `A, B, C, A, D, B, E`")
elif workload_category == "Custom Block String":
    raw_workload_string = st.sidebar.text_input(
        "Enter Storage Block Requests:",
        value="A, B, C, A, D, B, E",
        help="Separate blocks with commas, spaces, or tabs."
    )
else:
    # Synthetic generator parameters
    col_gen1, col_gen2 = st.sidebar.columns(2)
    with col_gen1:
        trace_len = st.number_input("Request Count:", min_value=10, max_value=100, value=25, step=5)
    with col_gen2:
        unique_blocks = st.number_input("Unique Blocks:", min_value=3, max_value=15, value=7, step=1)
    
    capacity_hint = st.sidebar.number_input("Target Cache Capacity:", min_value=1, max_value=16, value=3, step=1)
    
    if st.sidebar.button("🔄 Generate Fresh Trace"):
        st.session_state["synthetic_trace"] = generate_synthetic_workload(
            workload_category, count=trace_len, unique_blocks=unique_blocks, capacity=capacity_hint
        )

    if "synthetic_trace" not in st.session_state:
        st.session_state["synthetic_trace"] = generate_synthetic_workload(
            workload_category, count=trace_len, unique_blocks=unique_blocks, capacity=capacity_hint
        )
    raw_workload_string = ", ".join(st.session_state["synthetic_trace"])
    st.sidebar.caption(f"Generated Trace: `{raw_workload_string[:45]}...`")

# Cache Hardware Configuration
cache_capacity = st.sidebar.slider(
    "Cache Capacity (Slots / Blocks):",
    min_value=1,
    max_value=16,
    value=3,
    step=1,
    help="Number of block frames allocated in the controller cache."
)

algorithm_mode = st.sidebar.radio(
    "Algorithm Evaluation Mode:",
    ["Compare All (FIFO, LRU, LFU)", "FIFO Only", "LRU Only", "LFU Only"]
)

with st.sidebar.expander("⚡ Latency & Timing Parameters (Advanced)"):
    hit_latency = st.number_input("Cache Hit Latency (ms):", min_value=0.01, max_value=1.0, value=0.1, step=0.05,
                                  help="High-speed controller NVRAM/DRAM latency.")
    miss_latency = st.number_input("Cache Miss Latency (ms):", min_value=1.0, max_value=50.0, value=10.0, step=1.0,
                                   help="Backend disk / NVMe array fetch latency.")

st.sidebar.markdown("---")
st.sidebar.caption("SAN Architecture: Dual Active Controller with Write-Through / Read-Ahead Simulation Engine.")


# ---------------------------------------------------------
# Parsing & Input Validation
# ---------------------------------------------------------
requests = parse_requests(raw_workload_string)

if not requests:
    st.error("⚠️ Workload is empty. Please enter a valid sequence of block requests.")
    st.stop()


# ---------------------------------------------------------
# Header & SAN Controller Status
# ---------------------------------------------------------
st.markdown("## 🗄️ Storage Area Network (SAN) Cache Replacement Simulator")
st.markdown(
    "Benchmark and visualize how **FIFO**, **LRU**, and **LFU** replacement policies "
    "govern controller cache hit rates, eviction pressures, and storage I/O latency."
)

# Controller Hardware Banner
c_info1, c_info2, c_info3, c_info4 = st.columns(4)
c_info1.markdown(f"**Storage Workload:** `{len(requests)} I/O Requests`")
c_info2.markdown(f"**Cache Capacity:** `{cache_capacity} Blocks`")
c_info3.markdown(f"**Hit Latency:** `{hit_latency} ms` (NVRAM)")
c_info4.markdown(f"**Miss Latency:** `{miss_latency} ms` (Disk)")

st.markdown("---")


# ---------------------------------------------------------
# Simulation Execution
# ---------------------------------------------------------
if algorithm_mode == "Compare All (FIFO, LRU, LFU)":
    results: Dict[str, SimulationResult] = simulate_all(requests, cache_capacity, hit_latency, miss_latency)
    active_algo_keys = ["FIFO", "LRU", "LFU"]
else:
    selected_name = algorithm_mode.split()[0]
    if selected_name == "FIFO":
        res = simulate_fifo(requests, cache_capacity, hit_latency, miss_latency)
    elif selected_name == "LRU":
        res = simulate_lru(requests, cache_capacity, hit_latency, miss_latency)
    else:
        res = simulate_lfu(requests, cache_capacity, hit_latency, miss_latency)
    results = {selected_name: res}
    active_algo_keys = [selected_name]


# ---------------------------------------------------------
# 1. High-Level SAN Storage Performance Dashboard
# ---------------------------------------------------------
st.subheader("📊 Storage Controller Benchmark Summary")

summary_table = []
for name, res in results.items():
    summary_table.append({
        "Policy": name,
        "Total I/O": res.total_requests,
        "Hits": res.hits,
        "Misses": res.misses,
        "Evictions": res.replacements,
        "Hit Ratio (%)": f"{res.hit_ratio:.2f}%",
        "Miss Ratio (%)": f"{res.miss_ratio:.2f}%",
        "Effective Access Time": f"{res.effective_access_time_ms:.3f} ms",
        "Total I/O Time": f"{res.total_time_with_cache_ms:.1f} ms",
        "I/O Speedup": f"{res.speedup_factor:.2f}x"
    })

summary_df = pd.DataFrame(summary_table)
st.dataframe(summary_df, use_container_width=True, hide_index=True)

# Winner Banner
if len(results) > 1:
    best_algo = max(results.keys(), key=lambda k: (results[k].hit_ratio, -results[k].effective_access_time_ms))
    best_res = results[best_algo]
    st.success(
        f"🏆 **Top-Performing Policy:** **{best_algo}** delivered the highest efficiency with a "
        f"**{best_res.hit_ratio:.2f}% Hit Ratio**, saving **{best_res.time_saved_ms:.1f} ms** of storage latency "
        f"(**{best_res.speedup_factor:.2f}x faster** than uncached storage)."
    )

st.markdown("<br>", unsafe_allow_html=True)


# ---------------------------------------------------------
# 2. Matplotlib Analytics Suite
# ---------------------------------------------------------
st.subheader("📈 Storage Analytics & Visual Graphs")

if len(results) > 1:
    tab_graph1, tab_graph2, tab_graph3 = st.tabs([
        "📊 Hits vs. Misses & Hit Ratio",
        "⏱️ Cumulative Hit Ratio Over Time",
        "⚡ Effective Access Time & Latency"
    ])

    with tab_graph1:
        col_g1, col_g2 = st.columns(2)
        
        # Hits vs Misses Bar Chart
        with col_g1:
            fig, ax = plt.subplots(figsize=(6, 3.8))
            algos = list(results.keys())
            hits = [results[a].hits for a in algos]
            misses = [results[a].misses for a in algos]
            x = range(len(algos))
            width = 0.35

            b1 = ax.bar([i - width/2 for i in x], hits, width, label='Hits', color='#0284C7')
            b2 = ax.bar([i + width/2 for i in x], misses, width, label='Misses', color='#EF4444')

            ax.set_ylabel('I/O Operations', fontsize=10, fontweight='bold', color='#1E293B')
            ax.set_title('Cache Hits vs. Cache Misses', fontsize=11, fontweight='bold', color='#0F172A')
            ax.set_xticks(list(x))
            ax.set_xticklabels(algos, fontsize=10, fontweight='bold')
            ax.legend(frameon=True, facecolor='#FFFFFF')
            ax.grid(axis='y', linestyle='--', alpha=0.5)

            for bar in b1:
                h = bar.get_height()
                ax.annotate(f'{h}', (bar.get_x() + bar.get_width() / 2, h),
                            textcoords="offset points", xytext=(0, 3), ha='center', fontsize=9, fontweight='bold')
            for bar in b2:
                h = bar.get_height()
                ax.annotate(f'{h}', (bar.get_x() + bar.get_width() / 2, h),
                            textcoords="offset points", xytext=(0, 3), ha='center', fontsize=9, fontweight='bold')
            fig.tight_layout()
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

        # Hit Ratio Comparison
        with col_g2:
            fig, ax = plt.subplots(figsize=(6, 3.8))
            hit_ratios = [results[a].hit_ratio for a in algos]
            colors = ['#10B981', '#6366F1', '#F59E0B']
            bars = ax.bar(algos, hit_ratios, width=0.45, color=colors[:len(algos)])

            ax.set_ylabel('Hit Ratio (%)', fontsize=10, fontweight='bold', color='#1E293B')
            ax.set_title('Cache Hit Ratio Comparison (%)', fontsize=11, fontweight='bold', color='#0F172A')
            ax.set_ylim(0, max(max(hit_ratios) + 15, 100))
            ax.grid(axis='y', linestyle='--', alpha=0.5)

            for bar in bars:
                h = bar.get_height()
                ax.annotate(f'{h:.1f}%', (bar.get_x() + bar.get_width() / 2, h),
                            textcoords="offset points", xytext=(0, 3), ha='center', fontsize=9, fontweight='bold')
            fig.tight_layout()
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

    with tab_graph2:
        # Time-series cumulative hit ratio line chart
        fig, ax = plt.subplots(figsize=(10, 4.0))
        palette = {'FIFO': '#EF4444', 'LRU': '#0284C7', 'LFU': '#10B981'}
        markers = {'FIFO': 'o', 'LRU': 's', 'LFU': '^'}

        for name, res in results.items():
            steps_x = [s.step for s in res.steps]
            ratios_y = [s.cumulative_hit_ratio for s in res.steps]
            ax.plot(
                steps_x, ratios_y,
                label=f"{name} (Final: {res.hit_ratio:.1f}%)",
                color=palette.get(name, '#333333'),
                marker=markers.get(name, 'o'),
                linewidth=2.2,
                markersize=4.5
            )

        ax.set_xlabel('Storage Request Step (Time Progress)', fontsize=10, fontweight='bold')
        ax.set_ylabel('Cumulative Hit Ratio (%)', fontsize=10, fontweight='bold')
        ax.set_title('Real-Time Cache Convergence & Hit Ratio Progression', fontsize=11, fontweight='bold')
        ax.set_ylim(-2, 102)
        ax.grid(True, linestyle='--', alpha=0.6)
        ax.legend(frameon=True, loc='best')
        fig.tight_layout()
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

    with tab_graph3:
        # Effective Access Time & Latency Comparison
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.8))
        
        eat_vals = [results[a].effective_access_time_ms for a in algos]
        bars1 = ax1.bar(algos, eat_vals, color=['#3B82F6', '#8B5CF6', '#EC4899'], width=0.45)
        ax1.set_ylabel('Milliseconds (ms)', fontsize=10, fontweight='bold')
        ax1.set_title('Effective Access Time (Lower is Better)', fontsize=11, fontweight='bold')
        ax1.grid(axis='y', linestyle='--', alpha=0.5)
        for b in bars1:
            h = b.get_height()
            ax1.annotate(f'{h:.2f} ms', (b.get_x() + b.get_width() / 2, h),
                         textcoords="offset points", xytext=(0, 3), ha='center', fontsize=9, fontweight='bold')

        # Total Execution Time with Cache vs Uncached
        time_vals = [results[a].total_time_with_cache_ms for a in algos]
        uncached_time = results[algos[0]].total_time_without_cache_ms
        bars2 = ax2.bar(algos, time_vals, color='#059669', width=0.45, label='With Cache')
        ax2.axhline(uncached_time, color='#DC2626', linestyle='--', linewidth=1.8, label=f'Uncached ({uncached_time:.0f} ms)')
        ax2.set_ylabel('Total Duration (ms)', fontsize=10, fontweight='bold')
        ax2.set_title('Total Storage Latency vs. Uncached Disk', fontsize=11, fontweight='bold')
        ax2.legend(frameon=True)
        ax2.grid(axis='y', linestyle='--', alpha=0.5)
        for b in bars2:
            h = b.get_height()
            ax2.annotate(f'{h:.0f} ms', (b.get_x() + b.get_width() / 2, h),
                         textcoords="offset points", xytext=(0, 3), ha='center', fontsize=9, fontweight='bold')

        fig.tight_layout()
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

else:
    # Single algorithm analytics view
    single_res = list(results.values())[0]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.8))

    cats = ['Hits', 'Misses', 'Evictions']
    vals = [single_res.hits, single_res.misses, single_res.replacements]
    b = ax1.bar(cats, vals, color=['#0284C7', '#EF4444', '#F59E0B'], width=0.45)
    ax1.set_title(f'Request Distribution - {single_res.algorithm_name}', fontsize=11, fontweight='bold')
    ax1.grid(axis='y', linestyle='--', alpha=0.5)
    for bar in b:
        h = bar.get_height()
        ax1.annotate(f'{h}', (bar.get_x() + bar.get_width() / 2, h),
                     textcoords="offset points", xytext=(0, 3), ha='center', fontsize=9, fontweight='bold')

    ax2.plot([s.step for s in single_res.steps], [s.cumulative_hit_ratio for s in single_res.steps],
             color='#10B981', marker='o', linewidth=2)
    ax2.set_title('Cumulative Hit Ratio (%)', fontsize=11, fontweight='bold')
    ax2.set_xlabel('Step Number')
    ax2.set_ylim(-2, 102)
    ax2.grid(True, linestyle='--', alpha=0.5)

    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

st.markdown("---")


# ---------------------------------------------------------
# 3. Interactive Step-by-Step Scrubber & Memory Slot View
# ---------------------------------------------------------
st.subheader("🔍 Interactive Memory Slot Inspector & Time Scrubber")
st.caption("Scrub through each I/O request step to observe the physical cache slots and eviction decisions in real time.")

active_policy_for_scrub = st.selectbox(
    "Select Policy for Step-by-Step Inspection:",
    active_algo_keys,
    index=0
)
current_sim = results[active_policy_for_scrub]

step_selection = st.slider(
    "⏱️ Scrub to Request Step:",
    min_value=1,
    max_value=len(requests),
    value=len(requests),
    step=1
)

# Step details
step_data = current_sim.steps[step_selection - 1]

# Step Telemetry Header Card
col_tele1, col_tele2, col_tele3, col_tele4 = st.columns(4)
col_tele1.metric("Current Step", f"#{step_data.step} of {len(requests)}")
col_tele2.metric("Requested Block", f"'{step_data.block}'")
col_tele3.metric("I/O Status", step_data.status, delta="HIT" if step_data.status == "HIT" else "-MISS")
col_tele4.metric("Evicted Block", step_data.replaced if step_data.replaced else "None")

# Eviction Decision Explanation Box
if step_data.status == "HIT":
    st.info(f"💡 **Decision Log:** {step_data.eviction_reason}")
else:
    if step_data.replaced:
        st.warning(f"⚠️ **Eviction Triggered:** {step_data.eviction_reason}")
    else:
        st.info(f"📥 **Cold Placement:** {step_data.eviction_reason}")

# Graphical Representation of Cache Block Frames / Memory Slots
st.markdown("##### 🖥️ Physical Cache Frame Layout at this Step:")
slot_cols = st.columns(cache_capacity)

for slot_i in range(cache_capacity):
    with slot_cols[slot_i]:
        # Check if slot is occupied
        if slot_i < len(step_data.cache_state):
            block_name = step_data.cache_state[slot_i]
            # Match metadata
            meta = next((s for s in step_data.slot_details if s["block"] == block_name), None)
            freq_str = f"Freq: {meta['frequency']}" if meta else ""
            arrival_str = f"Arr: #{meta['arrival_step']}" if meta else ""

            # Highlight card if this block was the hit or just loaded
            is_active_block = (block_name == step_data.block)
            if is_active_block and step_data.status == "HIT":
                card_class = "slot-card slot-card-active-hit"
                badge = "<span class='badge-hit'>HIT</span>"
            elif is_active_block and step_data.status == "MISS":
                card_class = "slot-card slot-card-active-miss"
                badge = "<span class='badge-miss'>NEW</span>"
            else:
                card_class = "slot-card"
                badge = "<span style='font-size:0.75rem; color:#64748B;'>RESIDENT</span>"

            st.markdown(f"""
            <div class="{card_class}">
                <div class="slot-header">Slot #{slot_i + 1} &nbsp; {badge}</div>
                <div class="slot-block">{block_name}</div>
                <div class="slot-meta">{freq_str} &nbsp;|&nbsp; {arrival_str}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Empty frame
            st.markdown(f"""
            <div class="slot-card" style="opacity: 0.55; border: 1px dashed #94A3B8;">
                <div class="slot-header">Slot #{slot_i + 1}</div>
                <div class="slot-block" style="color: #94A3B8;">—</div>
                <div class="slot-meta">Empty Frame</div>
            </div>
            """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ---------------------------------------------------------
# 4. Full Tabular Trace & CSV Export
# ---------------------------------------------------------
st.subheader("📋 Comprehensive Simulation Trace Table")

tabs_trace = st.tabs([f"{k} Trace Table" for k in active_algo_keys])

for idx, k in enumerate(active_algo_keys):
    with tabs_trace[idx]:
        rows = []
        for s in results[k].steps:
            rows.append({
                "Step": s.step,
                "Block Requested": s.block,
                "Status": s.status,
                "Evicted Block": s.replaced if s.replaced else "-",
                "Cache State": " [ " + " | ".join(s.cache_state) + " ]",
                "Cumulative Hit Ratio": f"{s.cumulative_hit_ratio:.1f}%",
                "Eviction / Placement Logic": s.eviction_reason
            })
        df_trace = pd.DataFrame(rows)
        st.dataframe(df_trace, use_container_width=True, hide_index=True)

        # Download trace CSV
        csv_data = df_trace.to_csv(index=False).encode('utf-8')
        st.download_button(
            label=f"📥 Export {k} Trace (CSV)",
            data=csv_data,
            file_name=f"san_{k.lower()}_simulation_trace.csv",
            mime="text/csv",
            key=f"dl_{k}"
        )

st.markdown("---")


# ---------------------------------------------------------
# 5. SAN Storage Architecture Theory & Insights
# ---------------------------------------------------------
with st.expander("📚 Engineering Deep Dive: SAN Cache Replacement Policies"):
    st.markdown("""
    ### Why Cache Replacement Policies Matter in Enterprise SANs
    Modern enterprise SAN controllers (e.g. Dell PowerStore, NetApp ONTAP, Pure Storage FlashArray) 
    rely on tier-0 NVRAM/DRAM caches to absorb I/O bursts. Cache misses force physical read commands 
    across PCIe/NVMe fabrics or SAS interconnects, elevating latency from sub-millisecond to tens of milliseconds.

    #### 1. FIFO (First In First Out)
    - **Mechanism:** Treats cache frames as a circular queue. The block that was inserted earliest is evicted first.
    - **SAN Pitfall (Belady's Anomaly):** Counter-intuitively, increasing cache size under FIFO can sometimes *increase* 
      the number of page faults/misses because arrival sequence does not correlate with access frequency or recency.

    #### 2. LRU (Least Recently Used)
    - **Mechanism:** Leverages **Temporal Locality** (if a block was read recently, it is highly likely to be read again soon). 
      Evicts the block that has been idle the longest.
    - **SAN Application:** Excellent for relational database transaction logs and index blocks. However, susceptible to 
      cache pollution during sequential streaming scans (e.g. full-disk antivirus or backup jobs).

    #### 3. LFU (Least Frequently Used with FIFO Tie-Breaker)
    - **Mechanism:** Exploits **Frequency Locality** by tracking total reference counts. Evicts the block with the lowest access count.
    - **Tie-Breaker:** When multiple blocks share the minimum frequency, the oldest block (FIFO order) is selected for eviction.
    - **SAN Pitfall:** Without dynamic frequency aging/decay, historic hot blocks that are no longer requested can remain 
      stuck in the cache, starving newly emerging hot blocks.
    """)
