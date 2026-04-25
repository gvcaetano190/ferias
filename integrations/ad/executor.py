from __future__ import annotations

import json
import platform
import shutil
import subprocess
from pathlib import Path


AD_DIR = Path(__file__).resolve().parent


def bloquear_usuario_ad(usuario_ad: str) -> dict:
    return _run_powershell_script("bloquear_usuario.ps1", usuario_ad)


def desbloquear_usuario_ad(usuario_ad: str) -> dict:
    return _run_powershell_script("desbloquear_usuario.ps1", usuario_ad)


def consultar_usuario_ad(usuario_ad: str) -> dict:
    return _run_powershell_script("consultar_usuario.ps1", usuario_ad)


def consultar_usuarios_ad(usuarios_ad: list[str]) -> list[dict]:
    usuarios_limpos = [usuario.strip() for usuario in usuarios_ad if usuario and usuario.strip()]
    if not usuarios_limpos:
        return []

    payload = _run_powershell_script_with_json("consultar_usuarios.ps1", usuarios_limpos)
    if isinstance(payload, dict):
        return [_normalize_payload(payload, payload.get("usuario_ad", ""))]
    return [_normalize_payload(item, item.get("usuario_ad", "")) for item in payload]


def _run_powershell_script(script_name: str, usuario_ad: str) -> dict:
    script_path = AD_DIR / script_name
    shell_name = _resolve_powershell()
    if not shell_name:
        return _error_result(
            usuario_ad,
            "PowerShell não encontrado. Instale/use o PowerShell do Windows ou `pwsh`.",
        )

    command = [
        shell_name,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-UsuarioAd",
        usuario_ad,
    ]

    try:
        # O script devolve JSON para o Python interpretar sem depender de parsing frágil.
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
    except FileNotFoundError:
        return _error_result(usuario_ad, f"Executável PowerShell não encontrado: {shell_name}")
    except subprocess.SubprocessError as exc:
        return _error_result(usuario_ad, f"Falha ao executar PowerShell: {exc}")

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()

    if result.returncode != 0 and not stdout:
        return _error_result(
            usuario_ad,
            stderr or f"Script PowerShell retornou código {result.returncode}.",
        )

    if not stdout:
        return _error_result(usuario_ad, stderr or "Script não retornou saída JSON.")

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return _error_result(usuario_ad, f"Saída inválida do script: {stdout}")

    if stderr and payload.get("success"):
        payload["message"] = f"{payload.get('message', '')} | stderr: {stderr}".strip(" |")
    elif stderr and not payload.get("success") and not payload.get("message"):
        payload["message"] = stderr

    return _normalize_payload(payload, usuario_ad, stderr=stderr)


def _run_powershell_script_with_json(script_name: str, payload_obj: list[str]) -> list[dict] | dict:
    script_path = AD_DIR / script_name
    shell_name = _resolve_powershell()
    if not shell_name:
        return _error_result("", "PowerShell não encontrado. Instale/use o PowerShell do Windows ou `pwsh`.")

    command = [
        shell_name,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-UsuariosJson",
        json.dumps(payload_obj, ensure_ascii=False),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=240,
            check=False,
        )
    except FileNotFoundError:
        return _error_result("", f"Executável PowerShell não encontrado: {shell_name}")
    except subprocess.SubprocessError as exc:
        return _error_result("", f"Falha ao executar PowerShell: {exc}")

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()

    if result.returncode != 0 and not stdout:
        return _error_result("", stderr or f"Script PowerShell retornou código {result.returncode}.")
    if not stdout:
        return _error_result("", stderr or "Script não retornou saída JSON.")

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return _error_result("", f"Saída inválida do script: {stdout}")

    if stderr:
        if isinstance(payload, list):
            for item in payload:
                if item.get("success"):
                    item["message"] = f"{item.get('message', '')} | stderr: {stderr}".strip(" |")
        elif isinstance(payload, dict) and payload.get("success"):
            payload["message"] = f"{payload.get('message', '')} | stderr: {stderr}".strip(" |")

    return payload


def _resolve_powershell() -> str | None:
    # Em Windows, prioriza o PowerShell nativo para facilitar uso em máquinas padrão.
    if platform.system().lower() == "windows":
        for candidate in ("powershell", "pwsh"):
            if shutil.which(candidate):
                return candidate
        return None

    for candidate in ("pwsh", "powershell"):
        if shutil.which(candidate):
            return candidate
    return None


def _error_result(usuario_ad: str, message: str) -> dict:
    return {
        "success": False,
        "usuario_ad": usuario_ad,
        "ad_status": "ERRO",
        "vpn_status": "NP",
        "message": message,
        "user_found": False,
        "is_enabled": False,
        "is_in_printi_acesso": False,
        "already_in_desired_state": False,
    }


def _normalize_payload(payload: dict, usuario_ad: str, *, stderr: str = "") -> dict:
    message = payload.get("message", stderr or "Sem mensagem")
    if stderr and payload.get("success"):
        message = f"{payload.get('message', '')} | stderr: {stderr}".strip(" |")
    return {
        "success": bool(payload.get("success")),
        "usuario_ad": payload.get("usuario_ad", usuario_ad),
        "ad_status": payload.get("ad_status", "ERRO"),
        "vpn_status": payload.get("vpn_status", "NP"),
        "message": message,
        "user_found": bool(payload.get("user_found", False)),
        "is_enabled": bool(payload.get("is_enabled", False)),
        "is_in_printi_acesso": bool(payload.get("is_in_printi_acesso", False)),
        "already_in_desired_state": bool(payload.get("already_in_desired_state", False)),
    }
