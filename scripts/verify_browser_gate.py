"""Build and verify a disposable browser/Beat stack. Run with `make browser` (DEC-337)."""

import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    signal.signal(signal.SIGTERM, lambda signum, _frame: sys.exit(128 + signum))
    project = f"aegisops-browser-{secrets.token_hex(4)}"
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        web_port = reservation.getsockname()[1]
    env = os.environ | {
        "BROWSER_PROJECT": project,
        "BROWSER_WEB_PORT": str(web_port),
        "BROWSER_TEST_PASSWORD": secrets.token_urlsafe(24),
        "BROWSER_FAULT_SECRET": secrets.token_urlsafe(24),
        "POSTGRES_PASSWORD": secrets.token_urlsafe(24),
        "NEXT_TELEMETRY_DISABLED": "1",
        "PLAYWRIGHT_BROWSERS_PATH": str(ROOT / ".cache/ms-playwright"),
    }
    evidence = ROOT / "artifacts" / project
    evidence.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix=project) as temp:
        env_file = Path(temp) / "compose.env"
        env_file.write_text("")  # Do not load the developer's .env or touch existing stacks.
        compose = [
            "docker",
            "compose",
            "--env-file",
            str(env_file),
            "-p",
            project,
            "-f",
            "docker-compose.yml",
            "-f",
            "docker-compose.verify.yml",
            "-f",
            "docker-compose.browser.yml",
            "--profile",
            "core",
            "--profile",
            "lab",
        ]

        def run(
            args: list[str],
            *,
            capture: bool = False,
            input_text: str | None = None,
            timeout: int = 180,
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                args,
                cwd=ROOT,
                env=env,
                input=input_text,
                text=True,
                capture_output=capture,
                check=True,
                timeout=timeout,
            )

        try:
            print(f"Isolated release gate: {project}; evidence: {evidence}", flush=True)
            run(compose + ["config", "--quiet"])
            run(compose + ["build", "api", "shop-api"], timeout=600)
            run(compose + ["up", "-d", "--wait", "--wait-timeout", "90", "postgres", "redis"])
            run(compose + ["run", "--rm", "--no-deps", "api", "alembic", "upgrade", "head"])
            run(compose + ["up", "-d", "--wait", "--wait-timeout", "90", "api", "shop-api"])
            address = run(compose + ["port", "api", "8000"], capture=True).stdout.strip()
            assert address.startswith("127.0.0.1:"), f"Invalid loopback API binding: {address!r}"
            env["BROWSER_API_URL"] = f"http://{address}"
            print(f"Isolated API: {env['BROWSER_API_URL']}", flush=True)
            env["NEXT_PUBLIC_API_URL"] = env["BROWSER_API_URL"]
            env["API_URL"] = env["BROWSER_API_URL"]
            deadline = time.monotonic() + 30
            while True:
                try:
                    with urllib.request.urlopen(f"{env['BROWSER_API_URL']}/readyz", timeout=3) as r:
                        assert json.load(r)["checks"] == {"postgres": "ok", "redis": "ok"}
                    break
                except (
                    urllib.error.URLError,
                    TimeoutError,
                ):
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(1)
            fixture = (ROOT / "scripts/browser_gate_fixture.py").read_text()
            run(
                compose + ["exec", "-T", "api", "python", "-c", fixture, "seed"],
                input_text=env["BROWSER_TEST_PASSWORD"] + "\n",
            )
            run(compose + ["up", "-d", "--wait", "--wait-timeout", "90", "worker", "scheduler"])
            proof = run(
                compose + ["exec", "-T", "api", "python", "-u", "-c", fixture, "watchdog"],
                capture=True,
                timeout=120,
            )
            print(proof.stdout, flush=True)
            (evidence / "watchdog.txt").write_text(proof.stdout)
            scheduler_ids = run(
                compose + ["ps", "-q", "--status", "running", "scheduler"], capture=True
            ).stdout.split()
            assert len(scheduler_ids) == 1, "Exactly one running scheduler is required"
            run(
                compose
                + [
                    "exec",
                    "-T",
                    "scheduler",
                    "python",
                    "-c",
                    "import os; from pathlib import Path; "
                    "assert os.getuid() == 10001; "
                    "assert Path('/tmp/celerybeat-schedule').exists(); "
                    "print('PASS: Beat runs as UID 10001 with its schedule in /tmp')",
                ]
            )
            beat = run(compose + ["logs", "--no-color", "scheduler"], capture=True).stdout
            worker = run(compose + ["logs", "--no-color", "worker"], capture=True).stdout
            assert "Sending due task reconcile-simulation-expiry-periodic" in beat
            assert "PermissionError" not in beat
            assert "aegisops.reconcile_simulation_expiry" in worker and "succeeded" in worker
            assert "'cleaned_expired_runs': 1" in worker
            print(
                "PASS: one non-root Beat scheduler dispatched cleanup to the real worker",
                flush=True,
            )
            run(["npm", "run", "build"], timeout=300)
            run(["npm", "run", "test:web"], timeout=180)
            print(f"PASS: isolated browser and scheduler gate; logs: {evidence}", flush=True)
        finally:
            logs = subprocess.run(
                compose
                + ["logs", "--no-color", "--tail", "160", "api", "worker", "scheduler", "shop-api"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                timeout=30,
            )
            (evidence / "compose.log").write_text(logs.stdout + logs.stderr)
            run(compose + ["down", "--volumes", "--remove-orphans"], timeout=90)
            subprocess.run(
                ["docker", "image", "rm", f"{project}-api", f"{project}-shop-api"],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                timeout=30,
            )


if __name__ == "__main__":
    main()
