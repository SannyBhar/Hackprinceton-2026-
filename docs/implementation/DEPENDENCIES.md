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
