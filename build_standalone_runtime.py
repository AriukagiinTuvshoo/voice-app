import os
import shutil
import sys
import subprocess

def build_standalone_runtime(target_dir="runtime"):
    print(f"[*] Building standalone Python runtime in '{target_dir}'...")
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir, ignore_errors=True)
    os.makedirs(target_dir, exist_ok=True)

    py_root = sys.prefix
    print(f"[*] Source Python prefix: {py_root}")

    # 1. Copy core executables and DLLs from root
    core_files = [
        "python.exe", "pythonw.exe", "python312.dll", "python3.dll",
        "vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll"
    ]
    for fname in os.listdir(py_root):
        if fname.lower().endswith(".dll") or fname.lower() in [f.lower() for f in core_files]:
            src = os.path.join(py_root, fname)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(target_dir, fname))

    # 2. Copy DLLs directory
    dlls_src = os.path.join(py_root, "DLLs")
    if os.path.exists(dlls_src):
        shutil.copytree(dlls_src, os.path.join(target_dir, "DLLs"), ignore=shutil.ignore_patterns("*.pdb"))

    # 3. Copy tcl directory (needed for tkinter / FlowBar)
    tcl_src = os.path.join(py_root, "tcl")
    if os.path.exists(tcl_src):
        shutil.copytree(tcl_src, os.path.join(target_dir, "tcl"))

    # 4. Copy Lib directory (standard library and site-packages)
    lib_src = os.path.join(py_root, "Lib")
    lib_dest = os.path.join(target_dir, "Lib")
    
    # Exclude unnecessary caches and test suites to reduce installer size
    def ignore_bloat(path, names):
        ignored = set()
        for name in names:
            if name == "__pycache__":
                ignored.add(name)
            elif name in ("test", "tests") and "site-packages" not in path:
                ignored.add(name)
            elif name.endswith(".pyc") or name.endswith(".pdb"):
                ignored.add(name)
        return ignored

    shutil.copytree(lib_src, lib_dest, ignore=ignore_bloat)

    # 5. Verify isolated execution
    py_bin = os.path.join(target_dir, "python.exe")
    check_code = (
        "import sys, fastapi, uvicorn, edge_tts, sounddevice, miniaudio, pystray, PIL, tkinter; "
        "print('STANDALONE_OK:', sys.prefix == sys.base_prefix, 'PREFIX:', sys.prefix)"
    )
    res = subprocess.run([py_bin, "-c", check_code], capture_output=True, text=True)
    if res.returncode != 0:
        print("[!] Verification failed:")
        print("Stdout:", res.stdout)
        print("Stderr:", res.stderr)
        raise RuntimeError("Standalone runtime failed verification")
    
    print("[+] Runtime verified successfully:", res.stdout.strip())
    
    # Calculate size
    total_size = sum(
        os.path.getsize(os.path.join(dirpath, f))
        for dirpath, _, filenames in os.walk(target_dir)
        for f in filenames
    )
    print(f"[+] Total runtime directory size: {total_size / (1024*1024):.2f} MB")
    return True

if __name__ == "__main__":
    build_standalone_runtime()
