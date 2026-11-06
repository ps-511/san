"""
algorithms.py
=============
Enterprise-Grade SAN Cache Replacement Simulator Engine.

Features:
- Accurate implementations of FIFO, LRU, and LFU (with FIFO tie-breaking).
- SAN Hardware Latency Modeling (Effective Access Time, Speedup, Time Saved).
- Per-step cache slot introspection with detailed eviction explanations.
- Synthetic SAN Workload Generators (Zipfian OLTP, Sequential Scan, Thrashing, Random).
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
import re
import random


@dataclass
class StepResult:
    """Detailed telemetry for a single storage block I/O request."""
    step: int
    block: str
    status: str                         # "HIT" or "MISS"
    replaced: Optional[str]             # Name of evicted block or None
    cache_state: List[str]              # List of block tags currently in cache
    slot_details: List[Dict[str, Any]]  # Metadata per resident block (freq, recency, arrival)
    cumulative_hits: int
    cumulative_misses: int
    cumulative_hit_ratio: float
    eviction_reason: str                # Plain-English architectural justification


@dataclass
class SimulationResult:
    """Full benchmark results and hardware latency metrics for a simulation run."""
    algorithm_name: str
    requests: List[str]
    capacity: int
    total_requests: int
    hits: int
    misses: int
    replacements: int
    hit_ratio: float
    miss_ratio: float
    # Storage Latency Modeling (in milliseconds)
    hit_latency_ms: float
    miss_latency_ms: float
    effective_access_time_ms: float
    total_time_with_cache_ms: float
    total_time_without_cache_ms: float
    time_saved_ms: float
    speedup_factor: float
    steps: List[StepResult] = field(default_factory=list)


def parse_requests(raw_input: str) -> List[str]:
    """
    Parses arbitrary user input strings (commas, spaces, tabs, newlines)
    into a clean list of uppercase storage block identifiers.
    """
    if not raw_input or not raw_input.strip():
        return []
    tokens = re.split(r'[, \t\n\r]+', raw_input.strip())
    return [token.strip().upper() for token in tokens if token.strip()]


def generate_synthetic_workload(
    workload_type: str,
    count: int = 30,
    unique_blocks: int = 8,
    capacity: int = 3
) -> List[str]:
    """
    Generates realistic SAN storage access traces.
    
    Workload Profiles:
    - 'OLTP (Zipfian 80/20)': Highly skewed database transactions where ~20%
      of hot blocks receive ~80% of I/O operations.
    - 'Sequential Scan (Backup)': Cyclical, streaming block reads (e.g. backup/media).
    - 'Thrashing (Capacity + 1)': Working set size is exactly cache capacity + 1,
      inducing constant eviction.
    - 'Uniform Random I/O': Random un-cached distribution across storage LUN.
    """
    labels = [chr(65 + i) for i in range(min(unique_blocks, 26))]

    if workload_type == "OLTP (Zipfian 80/20)":
        # 80% of traffic goes to top 20% hot blocks (minimum 1 hot block)
        hot_count = max(1, int(len(labels) * 0.25))
        hot_blocks = labels[:hot_count]
        cold_blocks = labels[hot_count:]
        result = []
        for _ in range(count):
            if random.random() < 0.80 or not cold_blocks:
                result.append(random.choice(hot_blocks))
            else:
                result.append(random.choice(cold_blocks))
        return result

    elif workload_type == "Sequential Scan (Backup)":
        # Cyclical loop through all unique blocks
        return [labels[i % len(labels)] for i in range(count)]

    elif workload_type == "Thrashing (Capacity + 1)":
        # Loop over exactly (capacity + 1) blocks repeatedly
        loop_labels = labels[:min(capacity + 1, len(labels))]
        if len(loop_labels) < 2:
            loop_labels = ["A", "B", "C", "D"][:capacity + 1]
        return [loop_labels[i % len(loop_labels)] for i in range(count)]

    else:  # Uniform Random
        return [random.choice(labels) for _ in range(count)]


def _compute_latency_metrics(
    total: int,
    hits: int,
    misses: int,
    hit_latency: float,
    miss_latency: float
) -> Tuple[float, float, float, float, float, float, float]:
    """Calculates storage controller latency and speedup metrics."""
    if total <= 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0

    hit_ratio = round((hits / total) * 100.0, 2)
    miss_ratio = round((misses / total) * 100.0, 2)

    eat = round(((hit_ratio / 100.0) * hit_latency) + ((miss_ratio / 100.0) * miss_latency), 4)
    total_cached = round((hits * hit_latency) + (misses * miss_latency), 3)
    total_uncached = round(total * miss_latency, 3)
    time_saved = round(max(0.0, total_uncached - total_cached), 3)
    speedup = round(total_uncached / total_cached, 2) if total_cached > 0 else 1.0

    return hit_ratio, miss_ratio, eat, total_cached, total_uncached, time_saved, speedup


def simulate_fifo(
    requests: List[str],
    capacity: int,
    hit_latency: float = 0.1,
    miss_latency: float = 10.0
) -> SimulationResult:
    """
    Simulates FIFO (First In First Out) Cache Policy with deep hardware telemetry.
    """
    if capacity <= 0:
        raise ValueError("Cache capacity must be at least 1.")

    cache: List[str] = []
    arrival_step: Dict[str, int] = {}
    last_access_step: Dict[str, int] = {}
    access_counts: Dict[str, int] = {}

    steps: List[StepResult] = []
    hits = 0
    misses = 0
    replacements = 0

    for step_num, block in enumerate(requests, start=1):
        reason = ""
        if block in cache:
            hits += 1
            status = "HIT"
            replaced = None
            access_counts[block] += 1
            last_access_step[block] = step_num
            reason = f"Block '{block}' found in cache. Insertion order preserved under FIFO."
        else:
            misses += 1
            status = "MISS"
            access_counts[block] = 1
            last_access_step[block] = step_num

            if len(cache) < capacity:
                cache.append(block)
                arrival_step[block] = step_num
                replaced = None
                reason = f"Cold Miss: Cache has free capacity. Loaded block '{block}' into Slot #{len(cache)}."
            else:
                replaced = cache.pop(0)
                cache.append(block)
                arrival_step[block] = step_num
                replacements += 1
                evicted_arrival = arrival_step.pop(replaced, 0)
                reason = (f"Cache Full: Evicted oldest block '{replaced}' "
                          f"(loaded at Step #{evicted_arrival}). Allocated slot to '{block}'.")

        # Snapshot slot details
        slots = []
        for idx, resident in enumerate(cache):
            slots.append({
                "slot": idx + 1,
                "block": resident,
                "arrival_step": arrival_step.get(resident, 0),
                "last_access_step": last_access_step.get(resident, 0),
                "frequency": access_counts.get(resident, 1)
            })

        cum_hit_ratio = round((hits / step_num) * 100.0, 2)
        steps.append(StepResult(
            step=step_num,
            block=block,
            status=status,
            replaced=replaced,
            cache_state=list(cache),
            slot_details=slots,
            cumulative_hits=hits,
            cumulative_misses=misses,
            cumulative_hit_ratio=cum_hit_ratio,
            eviction_reason=reason
        ))

    total = len(requests)
    hr, mr, eat, t_cached, t_uncached, saved, speedup = _compute_latency_metrics(
        total, hits, misses, hit_latency, miss_latency
    )

    return SimulationResult(
        algorithm_name="FIFO (First In First Out)",
        requests=requests,
        capacity=capacity,
        total_requests=total,
        hits=hits,
        misses=misses,
        replacements=replacements,
        hit_ratio=hr,
        miss_ratio=mr,
        hit_latency_ms=hit_latency,
        miss_latency_ms=miss_latency,
        effective_access_time_ms=eat,
        total_time_with_cache_ms=t_cached,
        total_time_without_cache_ms=t_uncached,
        time_saved_ms=saved,
        speedup_factor=speedup,
        steps=steps
    )


def simulate_lru(
    requests: List[str],
    capacity: int,
    hit_latency: float = 0.1,
    miss_latency: float = 10.0
) -> SimulationResult:
    """
    Simulates LRU (Least Recently Used) Cache Policy.
    - End of the list represents the Most Recently Used (MRU) block.
    - Index 0 represents the Least Recently Used (LRU) block.
    """
    if capacity <= 0:
        raise ValueError("Cache capacity must be at least 1.")

    cache: List[str] = []
    arrival_step: Dict[str, int] = {}
    last_access_step: Dict[str, int] = {}
    access_counts: Dict[str, int] = {}

    steps: List[StepResult] = []
    hits = 0
    misses = 0
    replacements = 0

    for step_num, block in enumerate(requests, start=1):
        reason = ""
        if block in cache:
            hits += 1
            status = "HIT"
            replaced = None
            access_counts[block] += 1
            prev_last = last_access_step.get(block, step_num)
            last_access_step[block] = step_num
            # Move block to MRU position (end of list)
            cache.remove(block)
            cache.append(block)
            reason = (f"Cache Hit: Block '{block}' promoted to Most Recently Used (MRU). "
                      f"(Previous access was Step #{prev_last}).")
        else:
            misses += 1
            status = "MISS"
            access_counts[block] = 1
            last_access_step[block] = step_num

            if len(cache) < capacity:
                cache.append(block)
                arrival_step[block] = step_num
                replaced = None
                reason = f"Cold Miss: Allocated free Slot #{len(cache)} for block '{block}' (MRU)."
            else:
                replaced = cache.pop(0)  # Evict LRU at head
                cache.append(block)
                arrival_step[block] = step_num
                replacements += 1
                evicted_last = last_access_step.pop(replaced, 0)
                arrival_step.pop(replaced, 0)
                reason = (f"Cache Full: Evicted Least Recently Used block '{replaced}' "
                          f"(inactive since Step #{evicted_last}). Added '{block}' as MRU.")

        slots = []
        for idx, resident in enumerate(cache):
            slots.append({
                "slot": idx + 1,
                "block": resident,
                "arrival_step": arrival_step.get(resident, 0),
                "last_access_step": last_access_step.get(resident, 0),
                "frequency": access_counts.get(resident, 1)
            })

        cum_hit_ratio = round((hits / step_num) * 100.0, 2)
        steps.append(StepResult(
            step=step_num,
            block=block,
            status=status,
            replaced=replaced,
            cache_state=list(cache),
            slot_details=slots,
            cumulative_hits=hits,
            cumulative_misses=misses,
            cumulative_hit_ratio=cum_hit_ratio,
            eviction_reason=reason
        ))

    total = len(requests)
    hr, mr, eat, t_cached, t_uncached, saved, speedup = _compute_latency_metrics(
        total, hits, misses, hit_latency, miss_latency
    )

    return SimulationResult(
        algorithm_name="LRU (Least Recently Used)",
        requests=requests,
        capacity=capacity,
        total_requests=total,
        hits=hits,
        misses=misses,
        replacements=replacements,
        hit_ratio=hr,
        miss_ratio=mr,
        hit_latency_ms=hit_latency,
        miss_latency_ms=miss_latency,
        effective_access_time_ms=eat,
        total_time_with_cache_ms=t_cached,
        total_time_without_cache_ms=t_uncached,
        time_saved_ms=saved,
        speedup_factor=speedup,
        steps=steps
    )


def simulate_lfu(
    requests: List[str],
    capacity: int,
    hit_latency: float = 0.1,
    miss_latency: float = 10.0
) -> SimulationResult:
    """
    Simulates LFU (Least Frequently Used) Cache Policy.
    - Evicts block with lowest access frequency.
    - Tie-breaking Rule: FIFO order (earliest insertion time into cache).
    """
    if capacity <= 0:
        raise ValueError("Cache capacity must be at least 1.")

    cache: List[str] = []
    frequencies: Dict[str, int] = {}
    arrival_order: Dict[str, int] = {}
    last_access_step: Dict[str, int] = {}
    time_counter = 0

    steps: List[StepResult] = []
    hits = 0
    misses = 0
    replacements = 0

    for step_num, block in enumerate(requests, start=1):
        reason = ""
        if block in cache:
            hits += 1
            status = "HIT"
            frequencies[block] += 1
            last_access_step[block] = step_num
            replaced = None
            reason = f"Cache Hit: Incremented access frequency of block '{block}' to {frequencies[block]}."
        else:
            misses += 1
            status = "MISS"
            last_access_step[block] = step_num

            if len(cache) < capacity:
                cache.append(block)
                frequencies[block] = 1
                arrival_order[block] = time_counter
                time_counter += 1
                replaced = None
                reason = f"Cold Miss: Allocated free Slot #{len(cache)} for '{block}' (Initial frequency = 1)."
            else:
                # Find minimum frequency
                min_freq = min(frequencies[b] for b in cache)
                candidates = [b for b in cache if frequencies[b] == min_freq]

                if len(candidates) == 1:
                    victim = candidates[0]
                    tie_str = f"Lowest frequency ({min_freq} accesses)."
                else:
                    # FIFO tie-breaker: candidate that arrived earliest
                    victim = min(candidates, key=lambda b: arrival_order[b])
                    other_candidates = [c for c in candidates if c != victim]
                    tie_str = (f"Lowest frequency ({min_freq} accesses). Broke tie using FIFO: "
                               f"arrived at sequence order #{arrival_order[victim]} before {other_candidates}.")

                # Evict victim
                cache.remove(victim)
                del frequencies[victim]
                del arrival_order[victim]

                # Insert new block
                cache.append(block)
                frequencies[block] = 1
                arrival_order[block] = time_counter
                time_counter += 1

                replaced = victim
                replacements += 1
                reason = f"Cache Full: Evicted block '{replaced}' ({tie_str}). Loaded '{block}'."

        slots = []
        for idx, resident in enumerate(cache):
            slots.append({
                "slot": idx + 1,
                "block": resident,
                "arrival_step": arrival_order.get(resident, 0),
                "last_access_step": last_access_step.get(resident, 0),
                "frequency": frequencies.get(resident, 1)
            })

        cum_hit_ratio = round((hits / step_num) * 100.0, 2)
        steps.append(StepResult(
            step=step_num,
            block=block,
            status=status,
            replaced=replaced,
            cache_state=list(cache),
            slot_details=slots,
            cumulative_hits=hits,
            cumulative_misses=misses,
            cumulative_hit_ratio=cum_hit_ratio,
            eviction_reason=reason
        ))

    total = len(requests)
    hr, mr, eat, t_cached, t_uncached, saved, speedup = _compute_latency_metrics(
        total, hits, misses, hit_latency, miss_latency
    )

    return SimulationResult(
        algorithm_name="LFU (Least Frequently Used)",
        requests=requests,
        capacity=capacity,
        total_requests=total,
        hits=hits,
        misses=misses,
        replacements=replacements,
        hit_ratio=hr,
        miss_ratio=mr,
        hit_latency_ms=hit_latency,
        miss_latency_ms=miss_latency,
        effective_access_time_ms=eat,
        total_time_with_cache_ms=t_cached,
        total_time_without_cache_ms=t_uncached,
        time_saved_ms=saved,
        speedup_factor=speedup,
        steps=steps
    )


def simulate_all(
    requests: List[str],
    capacity: int,
    hit_latency: float = 0.1,
    miss_latency: float = 10.0
) -> Dict[str, SimulationResult]:
    """Runs FIFO, LRU, and LFU under identical workload conditions."""
    return {
        "FIFO": simulate_fifo(requests, capacity, hit_latency, miss_latency),
        "LRU": simulate_lru(requests, capacity, hit_latency, miss_latency),
        "LFU": simulate_lfu(requests, capacity, hit_latency, miss_latency)
    }
