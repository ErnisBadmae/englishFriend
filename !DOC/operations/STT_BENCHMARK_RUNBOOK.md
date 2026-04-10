# STT Benchmark Runbook

Last updated: 2026-04-10  
Scope: product-oriented STT comparison for the current voice loop

## Purpose

Use this runbook when you need one stable way to compare STT candidates without drifting away from the real product loop.

The benchmark is product-first, not WER-first.

We care about whether the transcript is good enough for:

- target-role capture
- recent-project capture
- technical-term capture
- low-fallback voice flow
- usable mission routing

## Current Tooling

The benchmark runner lives at:

- [scripts/run_stt_benchmark.py](../../scripts/run_stt_benchmark.py)

The current contract supports two input modes:

1. A single frontend debug export JSON from the dev panel.
2. A full benchmark cases JSON with multiple providers and observations.

## What Gets Scored

Each observation is scored on:

- `target_role_captured`
- `project_signal_captured`
- `technical_term_hits`
- `required_phrase_hits`
- `usable_transcript`
- `fallback_used`
- `overall_score`

Provider summary aggregates:

- average score
- average latency when present
- target-role capture rate
- project capture rate
- usable transcript rate
- fallback rate

## One-Off From Live Smoke

Use this mode right after a real browser smoke run.

Example:

```bash
python scripts/run_stt_benchmark.py \
  --voice-debug path/to/voice-debug-session.json \
  --case-id noisy-foundation-browser-vosk \
  --scenario noisy_foundation \
  --target-role-term "data scientist" \
  --project-term "recommendation model" \
  --technical-term "recommendation" \
  --required-phrase "improve grammar" \
  --output stt-benchmark-report.json
```

This mode reads:

- `session.sttProvider`
- sent user turns from `ws_text_sent`
- fallback usage through `source=composer`

## Multi-Provider Comparison

Use a JSON file when you want to compare multiple providers on the same benchmark case.

Minimal shape:

```json
{
  "cases": [
    {
      "case_id": "first-run-role-capture",
      "scenario": "first_run",
      "expected": {
        "target_role_terms": ["ml engineer"],
        "project_terms": ["churn prediction"],
        "technical_terms": ["churn", "prediction"]
      },
      "observations": [
        {
          "provider": "browser_vosk",
          "transcript": "I want an ML engineer job abroad. My recent project was churn prediction.",
          "latency_ms": 820,
          "source": "browser_vosk",
          "fallback_used": false
        },
        {
          "provider": "browser_whisper_webgpu",
          "transcript": "I want an ML engineer job abroad. My recent project was churn prediction.",
          "latency_ms": 610,
          "source": "browser_whisper_webgpu",
          "fallback_used": false
        }
      ]
    }
  ]
}
```

Run:

```bash
python scripts/run_stt_benchmark.py --cases path/to/stt-benchmark-cases.json
```

## Recommended Near-Term Benchmark Order

1. `browser_vosk`
2. `faster_whisper`
3. `parakeet_tdt`
4. `browser_whisper_webgpu`

Do not change product logic between candidates.

## Acceptance Criteria

Choose a shipping candidate only if it measurably improves at least one of:

- cleaner target-role capture
- cleaner project capture
- fewer composer fallbacks
- better technical-term capture
- lower time to usable transcript

Do not choose a provider only because it is fashionable or architecturally elegant.

## Non-Goals

This runbook does not yet include:

- automatic server-side audio benchmarking for every provider
- full WER/CER lab evaluation
- production storage for benchmark results
- automatic ingestion of backend logs into the benchmark report
