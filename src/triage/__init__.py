"""Alert triage with Jev: proof of concept and benchmark.

Pipeline (each stage reads the previous stage's newest file in results/):

    triage.dataset.generate  ->  data/
    triage.rules             ->  results/rules_<stamp>.json
    triage.jev               ->  results/jev_<stamp>.json
    triage.llm_estimate      ->  results/cost_<stamp>.json
    triage.evaluate          ->  results/summary.md
"""
