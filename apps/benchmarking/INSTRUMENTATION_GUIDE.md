# Multiagent Reasoner Instrumentation Guide

## Overview

The `multiagent_reasoner.py` system has been instrumented with comprehensive failure logging and analysis capabilities to help identify patterns in system behavior when it fails on multiplication problems.

## Key Features Added

### 1. Environment Variable Configuration

The system now supports environment variable overrides for easy tuning without code changes:

- `WINNING_VOTE_COUNT` (default: 2) - Number of votes needed to win
- `MAX_DEPTH` (default: 5) - Maximum recursion depth for decomposition
- `FINAL_TOKEN` (default: "vote:") - Token marking the final answer
- `LOG_FAILURES_JSONL` - Path to JSONL file for failure logging
- `LOG_DIR` - Directory for detailed per-run log files

### 2. Detailed Failure Logging

When a multiplication problem produces an incorrect answer, the system automatically logs:

- **Problem details**: Original problem text, expected answer, actual answer
- **Decomposition trace**: All candidate decompositions, voting results, winner
- **Solve trace**: Sub-problem solutions, composition candidates, voting results
- **Failure patterns**: Automatic classification of failure types
- **Configuration**: All tuning parameters used for the run
- **Log file path**: Link to detailed per-run log file (if LOG_DIR is set)

### 3. Failure Pattern Classification

The system automatically classifies failures into categories:

- `malformed_final` - Could not parse a number from the final answer
- `non_independent_subproblems` - P2 references P1, violating independence
- `ambiguous_composition_op` - Composition instruction contains conflicting operations
- `atomic_miscalc` - Error in atomic (non-decomposed) calculation
- `composed_miscalc` - Error in composed solution from sub-problems
- `unknown_failure` - Failure doesn't match known patterns

### 4. Per-Run Log Files

When `LOG_DIR` is set, each run creates a detailed log file with all INFO-level messages, making it easy to trace through the entire reasoning process for failed cases.

## Usage Examples

### Basic Usage (No Logging)

```bash
echo "What is 46048 × 42098?" | python3 apps/benchmarking/multiagent_reasoner.py
```

### With Failure Logging

```bash
export LOG_FAILURES_JSONL="/tmp/failures.jsonl"
export LOG_DIR="/tmp/mr_logs"
echo "What is 46048 × 42098?" | python3 apps/benchmarking/multiagent_reasoner.py
```

### With Custom Tuning Parameters

```bash
export WINNING_VOTE_COUNT=8
export MAX_DEPTH=3
export LOG_FAILURES_JSONL="/tmp/failures.jsonl"
export LOG_DIR="/tmp/mr_logs"
echo "What is 46048 × 42098?" | python3 apps/benchmarking/multiagent_reasoner.py
```

### With Benchmark Runner

```bash
export LOG_FAILURES_JSONL="./failures_wvc8.jsonl"
export LOG_DIR="./mr_logs"
export WINNING_VOTE_COUNT=8

python apps/benchmarking/agent_benchmark_runner.py \
  --python-prog apps/benchmarking/multiagent_reasoner.py \
  --task mul_5x5 \
  --local-jsonl data/bench_long_mul_5_5__200.jsonl \
  --answer-format number \
  --final-token '>>>>' \
  --timeout-ms 8000000 \
  --retries 1 \
  --sample-retries 2 \
  --num-workers 50 \
  --limit 10
```

**Note**: The benchmark runner uses `--final-token '>>>>'` but multiagent_reasoner uses `vote:` internally. The system will still work correctly as the runner extracts the final number.

## Analyzing Failure Logs

### View All Failures

```bash
cat failures.jsonl | jq '.'
```

### Count Failures by Pattern

```bash
cat failures.jsonl | jq -r '.failure_patterns[]' | sort | uniq -c | sort -rn
```

### View Specific Failure Details

```bash
cat failures.jsonl | jq 'select(.problem == "What is 46048 × 42098?")'
```

### Extract Problems with Non-Independent Subproblems

```bash
cat failures.jsonl | jq 'select(.failure_patterns[] | contains("non_independent"))'
```

### View Decomposition Candidates for Failures

```bash
cat failures.jsonl | jq '{problem, candidates: .trace.decomposition.candidates}'
```

### View Composition Voting Results

```bash
cat failures.jsonl | jq '{problem, votes: .trace.solve.composition_votes, winner: .trace.solve.composition_winner_idx}'
```

## Failure Log Format

Each failure is logged as a single JSON line with the following structure:

```json
{
  "problem": "What is 46048 × 42098?",
  "expected": 1938528704,
  "actual": 1938528705,
  "extracted_final": "1938528705",
  "final_resp": "... full agent response ...",
  "failure_patterns": ["composed_miscalc"],
  "trace": {
    "decomposition": {
      "candidates": ["P1=[...], P2=[...], C=[...]", ...],
      "winner_idx": 0,
      "votes": [2, 0, 1],
      "p1": "Calculate 46048 multiplied by 42000",
      "p2": "Calculate 46048 multiplied by 98",
      "c": "Add the results of P1 and P2"
    },
    "solve": {
      "s1_final": "1934016000",
      "s2_final": "4512704",
      "c": "Add the results of P1 and P2",
      "composed_candidates": ["1938528704", "1938528705", "1938528704"],
      "composition_votes": [2, 1, 0],
      "composition_winner_idx": 0
    }
  },
  "config": {
    "WINNING_VOTE_COUNT": 2,
    "MAX_DEPTH": 5,
    "CANDIDATE_COUNT": 3,
    "NUMBER_OF_VOTES": 3,
    "SOLUTION_CANDIDATE_COUNT": 3
  },
  "log_file": "/tmp/mr_logs/mr_12345_140123456789_1762109633.log"
}
```

## Observations from Initial Testing

### System Behavior

1. **Simple Problems (2-3 digits)**: The discriminator often chooses not to decompose (P2=[None], C=[None]) and solves atomically
2. **Complex Problems (5x5 digits)**: The system decomposes using strategies like:
   - Split by place value: 42098 = 42000 + 98
   - Split multiplicand: 46048 × 42098 = (46048 × 42000) + (46048 × 98)
3. **Recursive Decomposition**: Sub-problems are further decomposed until they're simple enough to solve atomically

### Potential Failure Patterns to Watch For

Based on the code review and initial testing:

1. **Incorrect Decomposition Math**: Choosing "add" when it should be "subtract" (e.g., 98 = 100 - 2)
2. **Non-Independent Subproblems**: P2 defined as "multiply result of P1 by 1000"
3. **Atomic Miscalculations**: LLM makes arithmetic errors on simple multiplications
4. **Composition Errors**: Misinterpreting composition instructions
5. **Voting Drift**: Wrong answer wins due to low vote count

## Recommendations for Analysis

1. **Start with WINNING_VOTE_COUNT=2** to see baseline failure patterns
2. **Increase to WINNING_VOTE_COUNT=8** to see which patterns persist
3. **Review failure logs** to identify common decomposition strategies that fail
4. **Check composition instructions** in failures to see if they're ambiguous
5. **Look for patterns** in the types of numbers that cause failures (e.g., numbers with many 9s, numbers close to powers of 10)

## Next Steps

1. Run benchmark with WINNING_VOTE_COUNT=2 and collect failures
2. Analyze failure patterns using the classification system
3. Run benchmark with WINNING_VOTE_COUNT=8 and compare results
4. Identify specific prompt improvements based on failure patterns
5. Consider adjusting agent prompts to address common failure modes
