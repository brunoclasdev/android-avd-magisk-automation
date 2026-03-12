#!/usr/bin/env python3
"""
Automatiza a criação de um AVD e o patch com Magisk via rootAVD.

Fluxo:
1) Garante SDK/paths.
2) (Opcional) instala system image via sdkmanager.
3) Cria o AVD se não existir.
4) Inicia o emulador com flags desejadas.
5) Espera ADB ficar online.
6) Executa rootAVD.sh e seleciona Magisk Stable.

Observação: o menu do rootAVD pode mudar; ajuste --magisk-choice se necessário.
"""

import argparse
import os
import platform
import subprocess
import sys
import time

DEFAULT_SDK = os.path.expanduser("~/Library/Android/Sdk")
DEFAULT_AVD = "Pentest_ARM2"
DEFAULT_API = "34"
DEFAULT_CHANNEL = "google_apis_playstore"
DEFAULT_PKG = "auto"
DEFAULT_PROXY = "http://127.0.0.1:8080"
DEFAULT_ROOTAVD = os.path.expanduser("~/tools/rootAVD/rootAVD.sh")


def run(cmd, env=None, check=True, capture=False, text=True, stdin=None):
    if capture:
        return subprocess.run(cmd, env=env, check=check, text=text, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return subprocess.run(cmd, env=env, check=check, text=text, stdin=stdin)


def find_sdk_tool(sdk, relpath):
    tool = os.path.join(sdk, relpath)
    if not os.path.exists(tool):
        return None
    return tool


def ensure_tools(sdk, require_runtime=True):
    tools = {
        "avdmanager": find_sdk_tool(sdk, "cmdline-tools/latest/bin/avdmanager"),
        "sdkmanager": find_sdk_tool(sdk, "cmdline-tools/latest/bin/sdkmanager"),
    }
    if require_runtime:
        tools["adb"] = find_sdk_tool(sdk, "platform-tools/adb")
        tools["emulator"] = find_sdk_tool(sdk, "emulator/emulator")

    missing = [k for k, v in tools.items() if v is None]
    if missing:
        print("Faltando ferramentas do SDK:")
        for k in missing:
            print(f"- {k}")
        print("Instale Android SDK Command-line Tools (latest).")
        if require_runtime:
            print("Depois rode novamente para baixar platform-tools/emulator.")
        sys.exit(1)
    return tools


def avd_exists(avdmanager, name):
    result = run([avdmanager, "list", "avd"], capture=True)
    return f"Name: {name}" in result.stdout


def create_avd(avdmanager, name, pkg, device):
    # avdmanager create avd -n NAME -k PKG -d DEVICE
    print(f"Criando AVD '{name}' com {pkg}...")
    run([avdmanager, "create", "avd", "-n", name, "-k", pkg, "-d", device], stdin=subprocess.PIPE)


def install_system_image(sdkmanager, pkg):
    print(f"Instalando system image: {pkg}")
    run([sdkmanager, "--install", pkg])


def install_sdk_packages(sdkmanager, api, pkg):
    packages = [
        "platform-tools",
        "emulator",
        f"platforms;android-{api}",
        pkg,
    ]
    print("Instalando dependencias do SDK:")
    for p in packages:
        print(f"- {p}")
    run([sdkmanager, "--install", *packages])


def start_emulator(emulator, name, proxy):
    cmd = [
        emulator,
        "-avd", name,
        "-writable-system",
        "-http-proxy", proxy,
        "-no-snapshot",
        "-no-snapshot-load",
    ]
    print("Iniciando emulador:", " ".join(cmd))
    # Inicia em background
    return subprocess.Popen(cmd)


def wait_for_device(adb, timeout=300):
    print("Aguardando ADB ficar online...")
    start = time.time()
    while time.time() - start < timeout:
        out = run([adb, "devices"], capture=True).stdout
        lines = [l.strip() for l in out.splitlines() if l.strip() and not l.startswith("List of")]
        if any("\tdevice" in l for l in lines):
            print("ADB online.")
            return True
        time.sleep(3)
    print("Timeout esperando ADB.")
    return False


def run_rootavd(rootavd, sdk, rel_ramdisk, magisk_choice):
    env = os.environ.copy()
    env["ANDROID_HOME"] = sdk
    cmd = [rootavd, rel_ramdisk]
    print("Executando rootAVD:", " ".join(cmd))
    # Envia escolha do menu (ex: '2' para Stable 30.6, '1' para local stable, '' para ENTER)
    choice = (magisk_choice + "\n").encode()
    proc = subprocess.Popen(cmd, env=env, stdin=subprocess.PIPE, stdout=sys.stdout, stderr=sys.stderr)
    try:
        proc.stdin.write(choice)
        proc.stdin.flush()
    except Exception:
        pass
    return proc.wait()


def read_avd_config(avd_name):
    cfg = os.path.expanduser(f"~/.android/avd/{avd_name}.avd/config.ini")
    if not os.path.exists(cfg):
        return {}
    data = {}
    with open(cfg, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data


def norm_rel(p):
    return p.replace("\\", "/").lstrip("/")


def resolve_ramdisk_relpath(sdk, avd_name, pkg):
    sdk_abs = os.path.abspath(sdk)
    candidates = []
    seen = set()

    cfg = read_avd_config(avd_name)
    sysdir_keys = sorted([k for k in cfg if k.startswith("image.sysdir.")])
    for key in sysdir_keys:
        sysdir = cfg[key]
        for rd in ("ramdisk.img", "ramdisk-qemu.img"):
            rel = norm_rel(os.path.join(sysdir, rd))
            if rel not in seen:
                seen.add(rel)
                candidates.append(rel)

    pkg_dir = norm_rel(pkg.replace(";", "/"))
    for rd in ("ramdisk.img", "ramdisk-qemu.img"):
        rel = norm_rel(os.path.join(pkg_dir, rd))
        if rel not in seen:
            seen.add(rel)
            candidates.append(rel)

    for rel in candidates:
        abs_path = os.path.join(sdk_abs, rel)
        if os.path.exists(abs_path):
            return rel

    print("Nao foi possivel localizar ramdisk para este AVD/pacote.")
    print("Caminhos tentados:")
    for rel in candidates:
        print(f"- {os.path.join(sdk_abs, rel)}")
    sys.exit(1)


def detect_host_abi():
    machine = platform.machine().lower()
    if machine in ("arm64", "aarch64"):
        return "arm64-v8a"
    if machine in ("x86_64", "amd64"):
        return "x86_64"
    return "arm64-v8a"


def resolve_pkg(pkg, api, channel):
    if pkg and pkg != "auto":
        return pkg
    abi = detect_host_abi()
    return f"system-images;android-{api};{channel};{abi}"


def validate_host_pkg(pkg):
    machine = platform.machine().lower()
    if machine in ("arm64", "aarch64") and "arm64-v8a" not in pkg:
        print("[aviso] Host ARM detectado (Apple Silicon).")
        print(f"[aviso] O pacote selecionado nao e arm64-v8a: {pkg}")
        print("[aviso] Prefira system-images;...;arm64-v8a para evitar incompatibilidade.")
    if machine in ("x86_64", "amd64") and "x86_64" not in pkg:
        print("[aviso] Host x86_64 detectado (macOS Intel).")
        print(f"[aviso] O pacote selecionado nao e x86_64: {pkg}")
        print("[aviso] Prefira system-images;...;x86_64 para melhor compatibilidade.")


def print_host_hardware():
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Darwin":
        if machine in ("arm64", "aarch64"):
            print("Host detectado: macOS Apple Silicon (arm64).")
            print("Recomendacao: usar AVD/imagen arm64-v8a.")
        elif machine in ("x86_64", "amd64"):
            print("Host detectado: macOS Intel (x86_64).")
            print("Recomendacao: usar AVD/imagen x86_64.")
        else:
            print(f"Host detectado: macOS ({machine}).")
    else:
        print(f"Host detectado: {system} ({machine}).")


def main():
    ap = argparse.ArgumentParser(
        epilog=(
            "Exemplos:\n"
            "  python3 how-to-magisk-emulator.py ehtmobile\n"
            "  python3 how-to-magisk-emulator.py --avd ehtmobile --pkg auto --api 34\n"
            "  python3 how-to-magisk-emulator.py --avd ehtmobile --pkg system-images;android-34;google_apis_playstore;arm64-v8a\n"
            "  python3 how-to-magisk-emulator.py -h"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    ap.add_argument(
        "target",
        nargs="?",
        help="atalho opcional: nome do AVD (ex: ehtmobile) ou package do system image (system-images;...)",
    )
    ap.add_argument("--sdk", default=DEFAULT_SDK)
    ap.add_argument("--avd", default=DEFAULT_AVD)
    ap.add_argument("--pkg", default=DEFAULT_PKG)
    ap.add_argument("--api", default=DEFAULT_API, help="API Android usada para montar pacote auto")
    ap.add_argument("--channel", default=DEFAULT_CHANNEL, help="canal da imagem (google_apis, google_apis_playstore, etc)")
    ap.add_argument("--device", default="pixel")
    ap.add_argument("--proxy", default=DEFAULT_PROXY)
    ap.add_argument("--rootavd", default=DEFAULT_ROOTAVD)
    ap.add_argument("--skip-sdk-download", action="store_true", help="nao baixar/atualizar pacotes do SDK automaticamente")
    ap.add_argument("--magisk-choice", default="2", help="opção do menu rootAVD (ex: 2 para Stable) ")
    ap.add_argument("--no-emulator", action="store_true", help="não iniciar o emulador (assume já rodando)")
    args = ap.parse_args()

    # Compatibilidade: permitir uso antigo com argumento posicional.
    if args.target:
        if args.target.startswith("system-images;"):
            args.pkg = args.target
        else:
            args.avd = args.target

    args.pkg = resolve_pkg(args.pkg, args.api, args.channel)
    sdk = os.path.expanduser(args.sdk)
    rootavd = os.path.expanduser(args.rootavd)
    print_host_hardware()
    print(f"System image selecionada: {args.pkg}")
    validate_host_pkg(args.pkg)

    if not os.path.exists(rootavd):
        print(f"rootAVD não encontrado em: {rootavd}")
        sys.exit(1)

    tools = ensure_tools(sdk, require_runtime=False)
    if not args.skip_sdk_download:
        install_sdk_packages(tools["sdkmanager"], args.api, args.pkg)
    tools = ensure_tools(sdk, require_runtime=True)

    if not avd_exists(tools["avdmanager"], args.avd):
        create_avd(tools["avdmanager"], args.avd, args.pkg, args.device)
    else:
        print(f"AVD '{args.avd}' já existe.")

    if not args.no_emulator:
        start_emulator(tools["emulator"], args.avd, args.proxy)

    if not wait_for_device(tools["adb"], timeout=300):
        sys.exit(1)

    rel_ramdisk = resolve_ramdisk_relpath(sdk, args.avd, args.pkg)
    print(f"Ramdisk selecionado: {rel_ramdisk}")
    rc = run_rootavd(rootavd, sdk, rel_ramdisk, args.magisk_choice)
    if rc != 0:
        print(f"rootAVD terminou com código {rc}")
        sys.exit(rc)

    print("Concluído. Faça Cold Boot no AVD e abra o app Magisk para finalizar.")


if __name__ == "__main__":
    main()
