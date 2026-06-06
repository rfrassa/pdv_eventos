"""
load_test.py — Prueba de carga para página estática en Netlify CDN
Uso: python load_test.py
Dependencias: solo stdlib de Python
"""

import concurrent.futures
import urllib.request
import time
import statistics

TARGET_URL = "https://spectacular-chebakia-0e02c0.netlify.app/"
STAGES = [50, 200, 500]
TIMEOUT_SECONDS = 15


def fetch(url: str) -> dict:
    """Realiza un único GET y devuelve status, tiempo en ms y tamaño en bytes."""
    start = time.perf_counter()
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "LoadTest/1.0 (ibat-pdv-eventos)"},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            body = resp.read()
            elapsed_ms = (time.perf_counter() - start) * 1000
            return {
                "status": resp.status,
                "ms": elapsed_ms,
                "bytes": len(body),
                "error": None,
            }
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "status": 0,
            "ms": elapsed_ms,
            "bytes": 0,
            "error": str(exc),
        }


def run_stage(concurrent_users: int) -> list[dict]:
    """Lanza `concurrent_users` peticiones en paralelo y devuelve los resultados."""
    print(f"\n{'='*60}")
    print(f"  Etapa: {concurrent_users} usuarios concurrentes")
    print(f"  URL:   {TARGET_URL}")
    print(f"{'='*60}")
    print("  Enviando peticiones...", flush=True)

    stage_start = time.perf_counter()
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_users) as executor:
        futures = [executor.submit(fetch, TARGET_URL) for _ in range(concurrent_users)]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    stage_elapsed = time.perf_counter() - stage_start
    print(f"  Etapa completada en {stage_elapsed:.2f}s", flush=True)
    return results, stage_elapsed


def print_summary(results: list[dict], stage_elapsed: float, concurrent_users: int) -> dict:
    """Calcula métricas e imprime la tabla resumen de la etapa."""
    total = len(results)
    successes = [r for r in results if r["status"] == 200]
    failures = [r for r in results if r["status"] != 200]

    success_count = len(successes)
    success_rate = (success_count / total * 100) if total > 0 else 0.0

    times_ms = [r["ms"] for r in results]
    success_times_ms = [r["ms"] for r in successes] if successes else [0]

    avg_ms = statistics.mean(times_ms) if times_ms else 0.0
    p50_ms = statistics.median(times_ms) if times_ms else 0.0

    sorted_times = sorted(times_ms)
    p95_index = max(0, int(len(sorted_times) * 0.95) - 1)
    p95_ms = sorted_times[p95_index] if sorted_times else 0.0
    max_ms = max(times_ms) if times_ms else 0.0

    throughput = total / stage_elapsed if stage_elapsed > 0 else 0.0

    avg_bytes = statistics.mean([r["bytes"] for r in successes]) if successes else 0

    print()
    print(f"  {'Métrica':<25} {'Valor':>12}")
    print(f"  {'-'*38}")
    print(f"  {'Total peticiones':<25} {total:>12}")
    print(f"  {'Exitosas (HTTP 200)':<25} {success_count:>12}")
    print(f"  {'Fallidas':<25} {len(failures):>12}")
    print(f"  {'Tasa de éxito':<25} {success_rate:>11.2f}%")
    print(f"  {'Tiempo promedio':<25} {avg_ms:>10.1f} ms")
    print(f"  {'Percentil 50 (p50)':<25} {p50_ms:>10.1f} ms")
    print(f"  {'Percentil 95 (p95)':<25} {p95_ms:>10.1f} ms")
    print(f"  {'Tiempo máximo':<25} {max_ms:>10.1f} ms")
    print(f"  {'Throughput':<25} {throughput:>9.1f} req/s")
    print(f"  {'Tamaño promedio resp.':<25} {avg_bytes:>9.0f} B")

    if failures:
        print()
        print("  Errores detectados:")
        error_counts: dict[str, int] = {}
        for r in failures:
            key = r["error"] or f"HTTP {r['status']}"
            error_counts[key] = error_counts.get(key, 0) + 1
        for err, count in error_counts.items():
            short_err = err[:60] + "..." if len(err) > 60 else err
            print(f"    [{count}x] {short_err}")

    return {
        "concurrent_users": concurrent_users,
        "total": total,
        "success_rate": success_rate,
        "avg_ms": avg_ms,
        "p50_ms": p50_ms,
        "p95_ms": p95_ms,
        "max_ms": max_ms,
        "throughput": throughput,
    }


def print_final_verdict(stage_summaries: list[dict]) -> None:
    """Imprime el veredicto final considerando todas las etapas."""
    print(f"\n{'='*60}")
    print("  VEREDICTO FINAL")
    print(f"{'='*60}")

    print(f"\n  {'Etapa':<10} {'Éxito %':>8} {'p95 ms':>9} {'Req/s':>8}  {'Resultado'}")
    print(f"  {'-'*55}")

    all_pass = True
    for s in stage_summaries:
        pass_stage = s["p95_ms"] < 2000 and s["success_rate"] > 99.0
        if not pass_stage:
            all_pass = False
        estado = "OK" if pass_stage else "FALLO"
        print(
            f"  {s['concurrent_users']:<10} "
            f"{s['success_rate']:>7.2f}% "
            f"{s['p95_ms']:>8.1f} "
            f"{s['throughput']:>8.1f}  "
            f"[{estado}]"
        )

    print()
    if all_pass:
        print("  >> CDN aguanta <<")
        print("     p95 < 2000ms y tasa de éxito > 99% en todas las etapas.")
    else:
        print("  >> revisar <<")
        print("     Una o más etapas superaron p95 >= 2000ms o tasa de éxito <= 99%.")
    print()


def main() -> None:
    print()
    print("  ╔══════════════════════════════════════════════════════╗")
    print("  ║   Prueba de Carga — Netlify CDN (stdlib Python)      ║")
    print("  ╚══════════════════════════════════════════════════════╝")
    print(f"\n  Objetivo: {TARGET_URL}")
    print(f"  Etapas:   {STAGES} usuarios concurrentes")
    print(f"  Timeout:  {TIMEOUT_SECONDS}s por petición")

    stage_summaries = []

    for users in STAGES:
        results, elapsed = run_stage(users)
        summary = print_summary(results, elapsed, users)
        stage_summaries.append(summary)

        if users != STAGES[-1]:
            print("\n  Pausa de 3s antes de la siguiente etapa...", flush=True)
            time.sleep(3)

    print_final_verdict(stage_summaries)


if __name__ == "__main__":
    main()
