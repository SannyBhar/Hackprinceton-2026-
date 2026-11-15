# Dependency maintenance (Phase 3 separate commit)

The starting lockfile reported 8 npm advisories: 2 critical, 4 high, 2 moderate. An isolated
maintenance commit updates Vite to 8.3.8, its React plugin to 6.3.0, Vitest to 5.1.0, and
React Router DOM to 7.18.5. React remains 18.3.1. Node >=22.12.0 is now required (verified on
Node 24.4.1). Playwright is pinned to 1.56.1. The existing BrowserRouter/Routes interface is
retained; tests/build/typecheck and browser workflows are rerun against the new lockfile.

`npm --prefix frontend audit --json` reports 0 vulnerabilities at verification time. This is
an npm advisory snapshot, not a comprehensive security guarantee. Backend optional OCR adds
Torch/Transformers/Pillow/protobuf/sentencepiece in a separate requirements file. Vision and
serial dependencies remain optional. PlatformIO board/framework/library versions are pinned.
The existing Starlette/AnyIO deprecation warning is documented; no unrelated backend framework
upgrade was bundled into feature work.

## Stabilization audit — 2026-11-14

No dependency manifests, pins or lockfiles were changed in this stabilization.
`npm --prefix frontend audit --json` returned zero vulnerabilities.
An isolated pip-audit 2.10.1 installation audited the existing Python 3.13 environment,
including optional OCR/vision/AI/serial dependencies, test tooling and pip. It returned
**133 advisory entries across 8 packages** (92 distinct advisory IDs; repeated IDs occur
in the service response). These remain unresolved and prevent a clean security gate.

| Installed package | Version | Reported entries |
| --- | --- | ---: |
| Pillow | 11.3.0 | 76 |
| pip (environment tooling) | 24.2 | 12 |
| protobuf (optional OCR) | 6.33.0 | 2 |
| pytest (test tooling) | 8.3.4 | 2 |
| python-multipart | 0.0.20 | 12 |
| Starlette (FastAPI dependency) | 0.41.3 | 14 |
| torch (optional OCR) | 2.9.1 | 5 |
| transformers (optional OCR) | 4.57.1 | 10 |

[The normalized audit result](PYTHON_AUDIT.json) preserves advisory IDs and reported fixed
versions without local paths. Fixed-version lists are advisory data, not a tested compatible
upgrade set. Resolve them in separately reviewed dependency maintenance with integration tests;
FastAPI/Starlette compatibility and local OCR model behavior need particular attention.
The Starlette/AnyIO deprecation warning also remains. The backend remains bound to localhost
in the Mac runner. Software test success is not a security clearance or physical acceptance.
