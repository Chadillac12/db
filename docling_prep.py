#!/usr/bin/env python3
"""
docling_prep.py - robust Docling wrapper for AnythingLLM ingestion.

Goals:
- Highest-fidelity extraction for technical docs (requirements/specs).
- All-local processing (no remote services enabled).
- Works on single file or entire directory (optional recursion).
- Preserves folder structure in output.
- Two-pass extraction + optional VLM fallback:
    1) standard pipeline
    2) force OCR retry if extracted text looks empty
    3) optional VLM fallback (granite_docling recommended) for PDFs/images that still look empty

Outputs:
- Markdown by default
- Optional JSON, YAML, text, doctags, html, etc
- image-export-mode referenced recommended for AnythingLLM

Notes:
- Classic .doc support is environment-dependent; .docx is strongly preferred.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
import time
from typing import Dict, Iterable, List, Optional, Tuple

# Best-effort extension filter; docling will still validate.
SUPPORTED_EXTS = {
    # Primary document types
    ".pdf", ".doc", ".docx", ".pptx", ".html", ".htm", ".md", ".csv", ".xlsx",
    # Images
    ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp",
    # Optional: subtitles / audio (docling supports asr pipeline)
    ".vtt", ".wav", ".mp3", ".m4a", ".mp4", ".mov",
}

# Heuristic thresholds
DEFAULT_MIN_ALPHA_CHARS = 300      # "too empty" if fewer letters than this in extracted md
DEFAULT_MIN_TOTAL_CHARS = 800      # "too empty" if fewer total chars than this in extracted md

# When to consider VLM fallback appropriate:
VLM_ELIGIBLE_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


@dataclass
class JobResult:
    src: Path
    ok: bool
    reason: str
    out_dir: Path
    md_path: Optional[Path] = None
    json_path: Optional[Path] = None
    used_force_ocr: bool = False
    used_vlm: bool = False
    duration_sec: float = 0.0


def run_cmd(cmd: List[str], cwd: Optional[Path] = None) -> Tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, shell=False, cwd=str(cwd) if cwd else None)
    return p.returncode, p.stdout, p.stderr


def count_alpha_chars(text: str) -> int:
    return sum(ch.isalpha() for ch in text)


def safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}"


def is_output_low_quality(md_text: str, min_alpha: int, min_total: int) -> bool:
    if not md_text:
        return True
    if len(md_text) < min_total:
        return True
    if count_alpha_chars(md_text) < min_alpha:
        return True
    return False


def find_output_file(out_dir: Path, src: Path, suffix: str) -> Optional[Path]:
    """
    Try to find the docling-produced output corresponding to src within out_dir.
    Docling naming can vary, so we search for:
    - filename starting with src.stem and ending with suffix
    - prefer the most recently modified match
    Optimized to avoid expensive deep rglob unless absolutely needed.
    """
    stem = src.stem
    # First pass: shallow search in the target folder
    candidates = list(out_dir.glob(f"{stem}*{suffix}"))
    if not candidates:
        candidates = list(out_dir.glob(f"*{suffix}"))
    # Second pass: one-level subfolders only (avoid full-tree scans)
    if not candidates:
        for child in out_dir.iterdir():
            if child.is_dir():
                candidates.extend(child.glob(f"{stem}*{suffix}"))
        if not candidates:
            for child in out_dir.iterdir():
                if child.is_dir():
                    candidates.extend(child.glob(f"*{suffix}"))
    # Last resort: deep search
    if not candidates:
        candidates = [p for p in out_dir.rglob(f"*{suffix}") if p.name.startswith(stem)]
    if not candidates:
        candidates = list(out_dir.rglob(f"*{suffix}"))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def load_password_map(path: Optional[Path]) -> Dict[str, str]:
    """
    JSON mapping of file path or basename -> password.
    Example:
    {
      "C:\\docs\\secret.pdf": "pass123",
      "secret2.pdf": "pw"
    }
    """
    if not path:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Password map JSON must be a dict of {path_or_name: password}.")
    return {str(k): str(v) for k, v in data.items()}


def resolve_pdf_password(src: Path, explicit: Optional[str], pw_map: Dict[str, str]) -> Optional[str]:
    if explicit:
        return explicit
    abs_key = str(src.resolve())
    if abs_key in pw_map:
        return pw_map[abs_key]
    if src.name in pw_map:
        return pw_map[src.name]
    return None


def build_docling_cmd(
    src: Path,
    out_dir: Path,
    to_formats: List[str],
    pipeline: str,
    vlm_model: Optional[str],
    asr_model: Optional[str],
    ocr_engine: str,
    ocr_lang: Optional[str],
    force_ocr: bool,
    tables: bool,
    table_mode: str,
    pdf_backend: str,
    pdf_password: Optional[str],
    device: str,
    num_threads: int,
    image_export_mode: str,
    debug_cells: bool,
    debug_ocr: bool,
    debug_layout: bool,
    debug_tables: bool,
    verbose: int,
) -> List[str]:
    cmd = ["docling", str(src)]

    cmd += ["--output", str(out_dir)]
    for fmt in to_formats:
        cmd += ["--to", fmt]

    # Pipelines
    cmd += ["--pipeline", pipeline]
    if pipeline == "vlm":
        if vlm_model:
            cmd += ["--vlm-model", vlm_model]
        else:
            # Default to the best local doc conversion model if not specified
            cmd += ["--vlm-model", "granite_docling"]
    if pipeline == "asr" and asr_model:
        cmd += ["--asr-model", asr_model]

    # OCR / tables
    cmd += ["--ocr-engine", ocr_engine]
    if ocr_lang:
        cmd += ["--ocr-lang", ocr_lang]
    if force_ocr:
        cmd += ["--force-ocr"]
    cmd += ["--tables" if tables else "--no-tables"]
    cmd += ["--table-mode", table_mode]

    # PDF specifics
    cmd += ["--pdf-backend", pdf_backend]
    if pdf_password:
        cmd += ["--pdf-password", pdf_password]

    # Export images for RAG
    cmd += ["--image-export-mode", image_export_mode]

    # Perf
    cmd += ["--device", device]
    cmd += ["--num-threads", str(num_threads)]

    # Debug visualization
    cmd += ["--debug-visualize-cells" if debug_cells else "--no-debug-visualize-cells"]
    cmd += ["--debug-visualize-ocr" if debug_ocr else "--no-debug-visualize-ocr"]
    cmd += ["--debug-visualize-layout" if debug_layout else "--no-debug-visualize-layout"]
    cmd += ["--debug-visualize-tables" if debug_tables else "--no-debug-visualize-tables"]

    # Verbosity (pass through verbatim)
    if verbose > 0:
        cmd += ["-" + "v" * verbose]

    # SECURITY / LOCAL-ONLY:
    # DO NOT add: --enable-remote-services
    # DO NOT add: --allow-external-plugins

    return cmd


def compute_output_subdir(out_root: Path, in_root: Path, src: Path) -> Path:
    """
    Preserve folder structure:
    out_root / relative_path_from_in_root / <outputs>
    """
    try:
        rel = src.resolve().relative_to(in_root.resolve())
        # drop filename; keep directory path
        rel_parent = rel.parent
    except Exception:
        rel_parent = Path("")
    return out_root / rel_parent


def convert_one(
    src: Path,
    in_root: Path,
    out_root: Path,
    to_formats: List[str],
    primary_pipeline: str,
    vlm_fallback: bool,
    vlm_model: Optional[str],
    asr_model: Optional[str],
    ocr_engine: str,
    ocr_lang: Optional[str],
    tables: bool,
    table_mode: str,
    pdf_backend: str,
    pdf_password: Optional[str],
    device: str,
    num_threads: int,
    image_export_mode: str,
    debug_cells: bool,
    debug_ocr: bool,
    debug_layout: bool,
    debug_tables: bool,
    verbose: int,
    min_alpha_chars: int,
    min_total_chars: int,
    ocr_retry_engine: str,
) -> JobResult:

    t0 = time.time()
    out_dir = compute_output_subdir(out_root, in_root, src)
    out_dir.mkdir(parents=True, exist_ok=True)

    def run_and_collect(pipeline: str, force_ocr: bool, ocr_engine_use: str) -> Tuple[int, str, str, Optional[Path], Optional[Path]]:
        cmd = build_docling_cmd(
            src=src,
            out_dir=out_dir,
            to_formats=to_formats,
            pipeline=pipeline,
            vlm_model=vlm_model,
            asr_model=asr_model,
            ocr_engine=ocr_engine_use,
            ocr_lang=ocr_lang,
            force_ocr=force_ocr,
            tables=tables,
            table_mode=table_mode,
            pdf_backend=pdf_backend,
            pdf_password=pdf_password,
            device=device,
            num_threads=num_threads,
            image_export_mode=image_export_mode,
            debug_cells=debug_cells,
            debug_ocr=debug_ocr,
            debug_layout=debug_layout,
            debug_tables=debug_tables,
            verbose=verbose,
        )
        rc, out, err = run_cmd(cmd)
        md_path = find_output_file(out_dir, src, ".md") if "md" in to_formats else None
        json_path = find_output_file(out_dir, src, ".json") if "json" in to_formats else None
        return rc, out, err, md_path, json_path

    # Pass 1: primary pipeline (default standard)
    rc1, out1, err1, md1, js1 = run_and_collect(primary_pipeline, force_ocr=False, ocr_engine_use=ocr_engine)
    if rc1 != 0:
        return JobResult(src=src, ok=False, reason=f"docling failed (pass1 {primary_pipeline}): {err1.strip()[:500]}", out_dir=out_dir)

    # Quality check (only if md produced)
    md_text = safe_read_text(md1) if md1 and md1.exists() else ""
    low_q = is_output_low_quality(md_text, min_alpha=min_alpha_chars, min_total=min_total_chars) if "md" in to_formats else False

    used_force = False
    used_vlm = False

    # Pass 2: force OCR retry if low quality
    if low_q:
        rc2, out2, err2, md2, js2 = run_and_collect(primary_pipeline, force_ocr=True, ocr_engine_use=ocr_retry_engine)
        if rc2 != 0:
            return JobResult(src=src, ok=False, reason=f"docling failed (pass2 force-ocr): {err2.strip()[:500]}", out_dir=out_dir)
        used_force = True
        md1, js1 = md2 or md1, js2 or js1
        md_text = safe_read_text(md1) if md1 and md1.exists() else ""
        low_q = is_output_low_quality(md_text, min_alpha=min_alpha_chars, min_total=min_total_chars) if "md" in to_formats else False

    # Pass 3: optional VLM fallback (for PDFs/images only) if still low quality
    if low_q and vlm_fallback and src.suffix.lower() in VLM_ELIGIBLE_EXTS:
        rc3, out3, err3, md3, js3 = run_and_collect("vlm", force_ocr=False, ocr_engine_use=ocr_engine)
        if rc3 != 0:
            return JobResult(src=src, ok=False, reason=f"docling failed (pass3 vlm fallback): {err3.strip()[:500]}", out_dir=out_dir)
        used_vlm = True
        md1, js1 = md3 or md1, js3 or js1

    # Validate required outputs exist for requested formats
    missing_outputs: List[str] = []
    if "md" in to_formats and not (md1 and md1.exists()):
        missing_outputs.append("md")
    if "json" in to_formats and not (js1 and js1.exists()):
        missing_outputs.append("json")

    duration = time.time() - t0

    if missing_outputs:
        return JobResult(
            src=src,
            ok=False,
            reason=f"missing outputs: {', '.join(missing_outputs)}",
            out_dir=out_dir,
            md_path=md1,
            json_path=js1,
            used_force_ocr=used_force,
            used_vlm=used_vlm,
            duration_sec=duration,
        )

    return JobResult(
        src=src,
        ok=True,
        reason="ok",
        out_dir=out_dir,
        md_path=md1,
        json_path=js1,
        used_force_ocr=used_force,
        used_vlm=used_vlm,
        duration_sec=duration,
    )


def iter_inputs(path: Path, recursive: bool) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    if recursive:
        yield from (p for p in path.rglob("*") if p.is_file())
    else:
        yield from (p for p in path.glob("*") if p.is_file())


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Prepare docs for AnythingLLM using Docling (local-only, robust).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("input", help="Input file or directory")
    ap.add_argument("--out", required=True, help="Output directory root")
    ap.add_argument("--recursive", action="store_true", help="Recurse into subfolders if input is a directory")

    ap.add_argument("--extensions", nargs="*", default=None,
                    help="Optional list of extensions to include (e.g., .pdf .docx). If omitted, uses built-in supported list.")
    ap.add_argument("--skip-existing", action="store_true",
                    help="Skip files that already have an output .md in the mirrored output folder.")

    # Output formats
    ap.add_argument("--to", nargs="+", default=["md"], choices=["md", "json", "yaml", "html", "text", "doctags", "html_split_page"],
                    help="Docling output formats (can specify multiple).")

    # Pipelines
    ap.add_argument("--pipeline", default="standard", choices=["standard", "legacy", "vlm", "asr"],
                    help="Primary pipeline used on pass 1 (recommend: standard).")
    ap.add_argument("--vlm-fallback", action="store_true",
                    help="If output looks empty after standard + force-ocr, retry with VLM pipeline (local).")
    ap.add_argument("--vlm-model", default="granite_docling",
                    choices=["smoldocling", "smoldocling_vllm", "granite_vision", "granite_vision_vllm", "granite_vision_ollama",
                             "got_ocr_2", "granite_docling", "granite_docling_vllm"],
                    help="VLM model for VLM fallback (recommend: granite_docling for best doc conversion).")
    ap.add_argument("--asr-model", default=None,
                    choices=["whisper_tiny", "whisper_small", "whisper_medium", "whisper_base", "whisper_large", "whisper_turbo",
                             "whisper_tiny_mlx", "whisper_small_mlx", "whisper_medium_mlx", "whisper_base_mlx", "whisper_large_mlx", "whisper_turbo_mlx",
                             "whisper_tiny_native", "whisper_small_native", "whisper_medium_native", "whisper_base_native", "whisper_large_native", "whisper_turbo_native"],
                    help="ASR model when --pipeline asr (rare for doc prep).")

    # OCR / tables
    ap.add_argument("--ocr-engine", default="auto",
                    help="OCR engine (auto, tesseract, etc).")
    ap.add_argument("--ocr-retry-engine", default="tesseract",
                    help="OCR engine used for the force-OCR retry (recommend: tesseract).")
    ap.add_argument("--ocr-lang", default=None, help="OCR language(s), comma-separated (engine-specific names).")
    ap.add_argument("--min-alpha-chars", type=int, default=DEFAULT_MIN_ALPHA_CHARS,
                    help="If extracted MD has fewer letters, treat as low-quality and retry.")
    ap.add_argument("--min-total-chars", type=int, default=DEFAULT_MIN_TOTAL_CHARS,
                    help="If extracted MD has fewer total chars, treat as low-quality and retry.")
    ap.add_argument("--tables", action="store_true", default=True, help="Enable table structure extraction.")
    ap.add_argument("--no-tables", dest="tables", action="store_false", help="Disable table structure extraction.")
    ap.add_argument("--table-mode", default="accurate", choices=["fast", "accurate"], help="Table extraction mode.")

    # PDF options
    ap.add_argument("--pdf-backend", default="dlparse_v4", choices=["pypdfium2", "dlparse_v1", "dlparse_v2", "dlparse_v4"],
                    help="PDF backend.")
    ap.add_argument("--pdf-password", default=None, help="Password for protected PDFs.")
    ap.add_argument("--pdf-password-map", default=None,
                    help="Path to JSON file mapping {absolute_path_or_basename: password} for PDFs.")

    # Export options
    ap.add_argument("--image-export-mode", default="referenced", choices=["placeholder", "embedded", "referenced"],
                    help="How images are exported (referenced is best for RAG).")

    # Debug visualizations
    ap.add_argument("--debug-cells", action="store_true", help="Visualize PDF cells (debug).")
    ap.add_argument("--debug-ocr", action="store_true", help="Visualize OCR cells (debug).")
    ap.add_argument("--debug-layout", action="store_true", help="Visualize layout clusters (debug).")
    ap.add_argument("--debug-tables", action="store_true", help="Visualize table cells (debug).")

    # Performance
    ap.add_argument("--workers", type=int, default=2,
                    help="Parallel workers (each worker runs a docling process).")
    ap.add_argument("--docling-threads", type=int, default=4,
                    help="--num-threads passed to docling per document.")
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "mps"],
                    help="Accelerator device.")
    ap.add_argument("-v", "--verbose", action="count", default=0,
                    help="Increase verbosity (-v or -vv).")

    args = ap.parse_args()

    if shutil.which("docling") is None:
        print("ERROR: 'docling' not found on PATH. Install: pip install docling", file=sys.stderr)
        return 2

    in_path = Path(args.input).expanduser()
    out_root = Path(args.out).expanduser()
    out_root.mkdir(parents=True, exist_ok=True)

    in_root = in_path if in_path.is_dir() else in_path.parent

    pw_map = load_password_map(Path(args.pdf_password_map)) if args.pdf_password_map else {}

    exts = set(e.lower() if e.startswith(".") else f".{e.lower()}" for e in (args.extensions or []))
    use_ext_filter = bool(args.extensions)

    # Build worklist
    worklist: List[Path] = []
    for p in iter_inputs(in_path, recursive=args.recursive):
        ext = p.suffix.lower()
        if ext not in SUPPORTED_EXTS:
            continue
        if use_ext_filter and ext not in exts:
            continue

        if args.skip_existing:
            out_dir = compute_output_subdir(out_root, in_root, p)
            existing_md = find_output_file(out_dir, p, ".md")
            if existing_md and existing_md.exists():
                continue

        worklist.append(p)

    if not worklist:
        print("No supported files found (or all skipped).", file=sys.stderr)
        return 1

    results: List[JobResult] = []

    total_jobs = len(worklist)
    start_time = time.time()

    # Early status output so the user sees activity before first file completes
    print(
        f"Starting {total_jobs} file(s) | workers={max(1, args.workers)} | threads/doc={args.docling_threads} "
        f"| device={args.device} | pipeline={args.pipeline} | vlm_fallback={args.vlm_fallback}",
        file=sys.stderr,
        flush=True,
    )

    # Heartbeat thread to emit periodic status before first completion
    heartbeat_stop = threading.Event()
    progress_state = {"completed": 0}

    def heartbeat() -> None:
        while not heartbeat_stop.wait(10):
            completed = progress_state["completed"]
            elapsed = time.time() - start_time
            rate = completed / elapsed if elapsed > 0 else 0
            remaining = total_jobs - completed
            eta_seconds = remaining / rate if rate > 0 else 0
            print(
                f"[heartbeat] [{completed}/{total_jobs}] elapsed={format_duration(elapsed)} eta={format_duration(eta_seconds)}",
                file=sys.stderr,
                flush=True,
            )

    hb_thread = threading.Thread(target=heartbeat, daemon=True)
    hb_thread.start()

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = []
        for src in worklist:
            pdf_pw = resolve_pdf_password(src, args.pdf_password, pw_map) if src.suffix.lower() == ".pdf" else None
            futs.append(ex.submit(
                convert_one,
                src=src,
                in_root=in_root,
                out_root=out_root,
                to_formats=args.to,
                primary_pipeline=args.pipeline,
                vlm_fallback=args.vlm_fallback,
                vlm_model=args.vlm_model,
                asr_model=args.asr_model,
                ocr_engine=args.ocr_engine,
                ocr_lang=args.ocr_lang,
                tables=args.tables,
                table_mode=args.table_mode,
                pdf_backend=args.pdf_backend,
                pdf_password=pdf_pw,
                device=args.device,
                num_threads=args.docling_threads,
                image_export_mode=args.image_export_mode,
                debug_cells=args.debug_cells,
                debug_ocr=args.debug_ocr,
                debug_layout=args.debug_layout,
                debug_tables=args.debug_tables,
                verbose=min(args.verbose, 2),
                min_alpha_chars=args.min_alpha_chars,
                min_total_chars=args.min_total_chars,
                ocr_retry_engine=args.ocr_retry_engine,
            ))

        completed = 0
        for f in as_completed(futs):
            result = f.result()
            results.append(result)
            completed += 1
            progress_state["completed"] = completed
            elapsed = time.time() - start_time
            rate = completed / elapsed if elapsed > 0 else 0
            remaining = total_jobs - completed
            eta_seconds = remaining / rate if rate > 0 else 0
            status_line = (
                f"[{completed}/{total_jobs}] "
                f"elapsed={format_duration(elapsed)} "
                f"eta={format_duration(eta_seconds)} "
                f"src={result.src.name} "
                f"{'OK' if result.ok else 'FAIL'}"
            )
            print(status_line, file=sys.stderr)

    heartbeat_stop.set()
    hb_thread.join(timeout=1)

    ok = [r for r in results if r.ok]
    bad = [r for r in results if not r.ok]
    force_count = sum(1 for r in ok if r.used_force_ocr)
    vlm_count = sum(1 for r in ok if r.used_vlm)
    durations = [r.duration_sec for r in results if r.duration_sec > 0]
    avg_duration = sum(durations) / len(durations) if durations else 0
    min_duration = min(durations) if durations else 0
    max_duration = max(durations) if durations else 0

    print(f"\nDone. Total: {len(results)}  OK: {len(ok)}  Failed: {len(bad)}")
    print(f"Force-OCR retries: {force_count}  VLM fallbacks: {vlm_count}")
    if durations:
        print(f"Durations (sec): avg={avg_duration:.1f}  min={min_duration:.1f}  max={max_duration:.1f}")

    if bad:
        print("\nFailures:")
        for r in bad:
            print(f" - {r.src} -> {r.reason}")

    # Exit non-zero if any failures
    return 0 if not bad else 3


if __name__ == "__main__":
    raise SystemExit(main())
