# Trismegistus Official Benchmark Staging

Updated: 2026-06-27

## Purpose

Stage public benchmark routes without blurring local receipts into public
leaderboard claims. Trismegistus should expose three route labels when scoring:

- `baseline-hermes`
- `tris-architecture-on`
- `tris-codex-helper`

## SWE-bench Verified

Status: official one-instance route proven.

- Harness: `swebench==4.1.0`
- External Colima profile: `s`
- Docker socket: `/Volumes/Samsung SSD 990 2TB/c/s/docker.sock`
- Instance: `astropy__astropy-12907`
- Compare receipt:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/data/swebench/swebench_verified_slice_20260622T194543Z_official_compare.md`

Current result:

- `baseline-hermes`: empty prediction, no evaluator error.
- `tris-architecture-on`: empty prediction after diff validation, no evaluator
  error.
- `tris-codex-helper`: completed `1`, resolved `1`, errors `0`.

Boundary:

This is not a leaderboard score. It is a one-instance official Verified
receipt proving the local external runner and helper repair loop.

Next gate:

Run a 5-instance SWE-bench Verified slice with the same three route labels.

## GAIA

Status: blocked on local Hugging Face auth/access.

- Browser account seen by operator:
  `https://huggingface.co/renaissancefieldlite`
- Local CLI check:
  `.venv-browser/bin/hf auth whoami` returns `Not logged in`.
- Local Python check:
  `LocalTokenNotFoundError`.
- Dataset gate:
  `gaia-benchmark/GAIA` is gated and needs a local token/session with access.

Next gate:

Run local `hf auth login` or set `HF_TOKEN` for the benchmark environment, then
verify GAIA dataset read before running any scoring slice.

## WebArena

Status: bounded homepage subset active and freshly re-verified; full domains
not staged locally.

Local bounded subset:

- Homepage app:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/vendor/webarena/environment_docker/webarena-homepage/app.py`
- Latest action trace:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/data/browser_autonomy/tris_browser_action_trace_20260627T120301Z.md`
- Compare receipt:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/data/eval_runs/webarena_action_compare_20260627T121510Z.md`
- Live public-web source sequence:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/data/browser_autonomy/tris_live_site_sequence_20260627T122726Z.md`
- Chat/field mission bridge smoke:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/data/field_missions/field_mission_20260627T123048Z509904.md`
- Seven-source live browser compare:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/data/eval_runs/live_browser_compare_20260627T132101Z.md`
- Promoted source/entity receipt:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/data/source_entities/live_source_entities_20260627T132323Z.md`
- Review-gated relationship draft packets:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/data/relationship_drafts/relationship_draft_packets_20260627T132528Z.md`
- Official readiness receipt:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/data/benchmark_gates/webarena_official_readiness_20260627T133524Z.md`

Current bounded results:

- WebArena homepage subset action trace: `ok=true`
- Calculator task: expression `67+6`, expected `73`, observed `73`
- Matched compare: `baseline-hermes=1.0`, `tris-architecture-on=1.0`,
  delta `0.0`
- Live browser source sequence: `7/7` loaded and `7/7` objective checks passed
- Normal chat route: source/browser request reached `field-mission` mode and
  saved Playwright/CDP browser receipts
- Seven-source captured-source compare: `baseline-hermes=0.987`,
  `tris-architecture-on=1.0`, mean delta `+0.013`, with no prompt or raw
  receipt spills
- Source promotion: `7` source entities and `6` review-gated relationship draft
  rows created; all drafts are `draft_not_sent`
- Relationship packets: `6` review-gated packets created; nothing sent

Official full-domain path from vendor docs:

- Recommended route: AWS AMI in `us-east-2`.
- AMI: `ami-08a862bf98e3bd7aa`
- Suggested instance: `t3a.xlarge`, `1000GB` EBS root.
- Services: shopping `7770`, shopping admin `7780`, GitLab `8023`,
  Wikipedia `8888`, forum `9999`, map `3000`, homepage `80`.

Local full-domain path:

- Requires downloading/loading large WebArena website images:
  shopping, shopping admin, forum, GitLab, Wikipedia/ZIM, map, and homepage.
- Current local Docker state does not include those website images.
- Current local endpoint check only has `HOMEPAGE` up at
  `http://127.0.0.1:4399`.
- Missing local domains:
  `SHOPPING`, `SHOPPING_ADMIN`, `REDDIT`, `GITLAB`, `WIKIPEDIA`, `MAP`.
- Current generated official task config count: `812`.
- Current auth state files under `vendor/webarena/.auth`: missing.
- Local `vendor/webarena/setup_env.sh` was corrected so `HOMEPAGE` points to
  `http://<host>:4399` instead of the placeholder `PASS`.
- AWS CLI and QEMU are installed locally.
- Paid AMI launch route is staged:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/scripts/aws/webarena_aws_launch.sh`
- AMI service-start route is staged:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/scripts/aws/webarena_aws_start_services.sh`
- Official local runner wrapper is staged:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/scripts/aws/webarena_official_local_runner.sh`
- AWS credential state: blocked until `aws login` or equivalent account
  credentials are present locally.

Next gate:

Use the paid AWS AMI official route for speed:

1. Authenticate AWS for the Inception-backed account.
2. Run `scripts/aws/webarena_aws_launch.sh`.
3. Run `scripts/aws/webarena_aws_start_services.sh`.
4. Run `scripts/aws/webarena_official_local_runner.sh`.

Boundary: this is still staging until `vendor/webarena/run.py` writes result
artifacts against live AMI domains. Do not claim an official WebArena score
before that.

Local fallback remains possible but lower priority: the downloadable official
assets are roughly `283GB` before map, and the prior SSD-backed x86 Colima
attempt hit a Unix socket path-length issue.

## Public Copy Boundary

Use `AI Partner / Expert Architecture`, not `AI agent`, in public-facing copy.

Do not claim:

- GAIA score before local HF access and official run.
- WebArena full score before full domains are live.
- SWE-bench score beyond the exact evaluated instance count.

Do claim, when backed by receipts:

- Tris has an official SWE-bench Verified one-instance helper-loop receipt.
- Tris has a bounded WebArena homepage browser-action trace.
- Tris has a staged benchmark plan across SWE-bench, WebArena, and GAIA.
