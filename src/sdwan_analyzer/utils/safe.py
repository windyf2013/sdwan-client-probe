import subprocess

def safe_run(cmd: list[str] | str, timeout: int = 5, encoding: str = "gbk") -> str | None:
    try:
        return subprocess.check_output(
            cmd,
            text=True,
            timeout=timeout,
            encoding=encoding,
            errors="ignore",
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL
        )
    except:
        return None