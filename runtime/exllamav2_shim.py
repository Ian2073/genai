"""
exllamav2 kernel shim for auto_gptq compatibility.
"""

import logging
import os
import re
import shutil
import sys
import torch
import types

logger = logging.getLogger(__name__)

_EXTENSION_NAME = "exllamav2_ext"
_COMPILER_SIGNATURE_STAMP = ".genai_msvc_signature.txt"


def _parse_msvc_version(cl_path):
    match = re.search(r"[\\/]MSVC[\\/](\d+)\.(\d+)\.(\d+)[\\/]", cl_path)
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _parse_vs_major(cl_path):
    match = re.search(r"Microsoft Visual Studio[\\/](\d+)[\\/]", cl_path)
    if not match:
        fallback = re.search(r"BuildTools(\d+)", cl_path, re.IGNORECASE)
        if not fallback:
            return None
        return int(fallback.group(1))
    return int(match.group(1))


def _collect_msvc_cl_paths():
    import glob

    candidates = []
    patterns = [
        r"C:\Program Files\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\HostX64\x64\cl.exe",
        r"C:\Program Files\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
        r"C:\Program Files (x86)\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\HostX64\x64\cl.exe",
        r"C:\Program Files (x86)\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
        r"C:\BuildTools*\VC\Tools\MSVC\*\bin\HostX64\x64\cl.exe",
        r"C:\BuildTools*\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
    ]
    for pattern in patterns:
        for cl_path in glob.glob(pattern):
            if os.path.isfile(cl_path):
                candidates.append(cl_path)
    return sorted(set(candidates))


def _choose_msvc_host_compiler(cl_paths):
    records = []
    for cl_path in cl_paths:
        version = _parse_msvc_version(cl_path)
        if version is not None:
            records.append((version, _parse_vs_major(cl_path), cl_path))

    if not records:
        return None, None, None

    # Prefer the highest compiler under VS17 for best ABI compatibility with installed PyTorch wheels.
    fallback_vs17 = [(v, vs, p) for v, vs, p in records if vs is None or vs <= 17]
    if fallback_vs17:
        version, vs_major, cl_path = max(fallback_vs17, key=lambda item: item[0])
        return cl_path, version, vs_major

    # Last resort: highest available compiler.
    version, vs_major, cl_path = max(records, key=lambda item: item[0])
    return cl_path, version, vs_major


def _compiler_signature(cl_path, version):
    normalized = os.path.normcase(os.path.normpath(cl_path))
    if not version:
        return normalized
    return f"{normalized}|{version[0]}.{version[1]}.{version[2]}"


def _invalidate_stale_extension_cache(cl_path, version):
    """Drop stale torch extension objects when host compiler selection changes.

    exllamav2 JIT can reuse cached .o files under torch_extensions. If those
    objects were produced by a different MSVC toolset (for example before/after
    VS upgrades), link can fail with unresolved internal STL helper symbols.
    """

    try:
        from torch.utils.cpp_extension import _get_build_directory

        build_dir = _get_build_directory(_EXTENSION_NAME, False)
    except Exception:
        return

    if not build_dir or not os.path.isdir(build_dir):
        return

    stamp_path = os.path.join(build_dir, _COMPILER_SIGNATURE_STAMP)
    new_signature = _compiler_signature(cl_path, version)
    previous_signature = None

    if os.path.isfile(stamp_path):
        try:
            previous_signature = open(stamp_path, "r", encoding="utf-8").read().strip() or None
        except Exception:
            previous_signature = None

    try:
        entries = os.listdir(build_dir)
    except Exception:
        entries = []

    has_build_artifacts = any(
        name.endswith((".o", ".obj", ".pyd", ".lib", ".exp", ".ninja_deps", ".ninja_log"))
        for name in entries
    )

    should_purge = False
    purge_reason = None
    if previous_signature and previous_signature != new_signature:
        should_purge = True
        purge_reason = "compiler signature changed"
    elif not previous_signature and has_build_artifacts:
        should_purge = True
        purge_reason = "legacy cache without compiler stamp"

    if should_purge:
        try:
            shutil.rmtree(build_dir)
            os.makedirs(build_dir, exist_ok=True)
            logger.info(
                "Purged stale exllamav2 torch extension cache (%s): %s",
                purge_reason,
                build_dir,
            )
        except Exception as exc:
            logger.warning("Failed to purge stale exllamav2 cache at %s: %s", build_dir, exc)

    try:
        with open(stamp_path, "w", encoding="utf-8") as fp:
            fp.write(new_signature)
    except Exception:
        pass


def _setup_jit_environment():
    import glob

    force_jit = os.environ.get("GENAI_FORCE_EXLLAMAV2_JIT", "").strip().lower() in {"1", "true", "yes", "on"}

    # Ensure helper executables (such as ninja.exe) from the active Python environment
    # are discoverable even when the parent shell PATH does not include venv Scripts.
    python_bin_dir = os.path.dirname(sys.executable)
    current_path = os.environ.get("PATH", "")
    if python_bin_dir and python_bin_dir not in current_path:
        os.environ["PATH"] = python_bin_dir + ";" + current_path
    ninja_candidate = os.path.join(python_bin_dir, "ninja.exe")
    if os.path.isfile(ninja_candidate) and "CMAKE_MAKE_PROGRAM" not in os.environ:
        os.environ["CMAKE_MAKE_PROGRAM"] = ninja_candidate

    if os.environ.get("GENAI_SKIP_EXLLAMAV2_JIT", "").strip().lower() in {"1", "true", "yes", "on"}:
        logger.info("GENAI_SKIP_EXLLAMAV2_JIT is enabled; skip exllamav2 JIT setup.")
        return False

    if not os.environ.get("CUDA_PATH"):
        cuda_base = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA"
        if os.path.isdir(cuda_base):
            cuda_versions = sorted(glob.glob(os.path.join(cuda_base, "v*")), reverse=True)
            if cuda_versions:
                os.environ["CUDA_PATH"] = cuda_versions[0]
                logger.info("Set CUDA_PATH=%s", cuda_versions[0])

    cuda_path = os.environ.get("CUDA_PATH", "")
    cuda_bin = os.path.join(cuda_path, "bin")
    if cuda_path and cuda_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = cuda_bin + ";" + os.environ.get("PATH", "")

    if not shutil.which("nvcc"):
        logger.warning("nvcc not found; skip exllamav2 JIT and use AutoGPTQ fallback")
        return False

    if not os.environ.get("TORCH_CUDA_ARCH_LIST"):
        try:
            cc = torch.cuda.get_device_capability()
            arch = f"{cc[0]}.{cc[1]}"
            os.environ["TORCH_CUDA_ARCH_LIST"] = arch
            logger.info("Set TORCH_CUDA_ARCH_LIST=%s", arch)
        except Exception:
            pass

    cl_candidates = _collect_msvc_cl_paths()
    selected_cl, selected_version, selected_vs_major = _choose_msvc_host_compiler(cl_candidates)

    if selected_cl:
        _invalidate_stale_extension_cache(selected_cl, selected_version)

        cl_dir = os.path.dirname(selected_cl)
        current_path = os.environ.get("PATH", "")
        if cl_dir not in current_path:
            os.environ["PATH"] = cl_dir + ";" + current_path

        # Prefer runtime libraries from the same MSVC toolset as cl.exe.
        msvc_root = os.path.dirname(os.path.dirname(os.path.dirname(cl_dir)))
        msvc_lib_dir = os.path.join(msvc_root, "lib", "x64")
        if os.path.isdir(msvc_lib_dir):
            current_lib = os.environ.get("LIB", "")
            if msvc_lib_dir not in current_lib:
                os.environ["LIB"] = msvc_lib_dir + ((";" + current_lib) if current_lib else "")

        os.environ["CUDAHOSTCXX"] = selected_cl
        os.environ["CXX"] = selected_cl
        prepend_flags = os.environ.get("NVCC_PREPEND_FLAGS", "").strip()
        if not re.search(r"(^|\s)-ccbin(\s|=)", prepend_flags, re.IGNORECASE):
            ccbin_value = selected_cl.replace("\\", "/")
            ccbin_flag = f"-ccbin {ccbin_value}"
            os.environ["NVCC_PREPEND_FLAGS"] = (ccbin_flag + " " + prepend_flags).strip()
        logger.info(
            "Selected MSVC host compiler for nvcc: %s (VS %s, toolset %s.%s.%s)",
            selected_cl,
            str(selected_vs_major) if selected_vs_major is not None else "unknown",
            selected_version[0],
            selected_version[1],
            selected_version[2],
        )

        unsupported_reason = None
        if selected_vs_major is not None and selected_vs_major >= 18:
            unsupported_reason = f"Visual Studio {selected_vs_major}"
        elif selected_version[0] > 14:
            unsupported_reason = f"MSVC toolset {selected_version[0]}.{selected_version[1]}.{selected_version[2]}"

        # CUDA 12.8 can reject newer 14.4x toolsets even under VS17.
        # Keep the newer toolset for ABI compatibility and add NVCC override flag.
        if selected_version[0] == 14 and selected_version[1] >= 40:
            prepend_flags = os.environ.get("NVCC_PREPEND_FLAGS", "")
            if "-allow-unsupported-compiler" not in prepend_flags:
                os.environ["NVCC_PREPEND_FLAGS"] = (prepend_flags + " -allow-unsupported-compiler").strip()
            logger.warning(
                "Using MSVC %s.%s.%s with CUDA compatibility override (-allow-unsupported-compiler).",
                selected_version[0],
                selected_version[1],
                selected_version[2],
            )

        if unsupported_reason:
            prepend_flags = os.environ.get("NVCC_PREPEND_FLAGS", "")
            if "-allow-unsupported-compiler" not in prepend_flags:
                os.environ["NVCC_PREPEND_FLAGS"] = (prepend_flags + " -allow-unsupported-compiler").strip()
            if not force_jit:
                logger.warning(
                    "Detected unsupported host compiler (%s); skip exllamav2 JIT and use AutoGPTQ fallback "
                    "(set GENAI_FORCE_EXLLAMAV2_JIT=1 to force compile).",
                    unsupported_reason,
                )
                return False
            logger.warning(
                "Detected unsupported host compiler (%s); forcing exllamav2 JIT with -allow-unsupported-compiler.",
                unsupported_reason,
            )
        return True

    if not shutil.which("cl"):
        logger.warning("MSVC cl.exe not found; skip exllamav2 JIT and use AutoGPTQ fallback")
        return False

    return force_jit


def setup_exllamav2_shim():
    if "exllamav2_kernels" in sys.modules:
        logger.debug("exllamav2_kernels already in sys.modules")
        return True

    should_try_jit = _setup_jit_environment()
    if not should_try_jit:
        return False

    try:
        from exllamav2 import ext

        ext_c = ext.ext_c
    except Exception as exc:
        logger.warning("Failed to load exllamav2 JIT kernels: %s", exc)
        return False

    if ext_c is None:
        logger.warning("exllamav2 ext_c is None — JIT compilation may have failed")
        return False

    if not hasattr(ext_c, "make_q_matrix") or not hasattr(ext_c, "gemm_half_q_half"):
        logger.warning("exllamav2 ext_c missing required functions")
        return False

    none_tensor = torch.empty((1, 1), device="meta")
    original_make_q_matrix = ext_c.make_q_matrix

    def make_q_matrix_compat(*args):
        if len(args) == 13:
            return original_make_q_matrix(*args)
        if len(args) == 10:
            (qweight, q_perm, q_invperm, q_scale, q_scale_max, q_groups, qzeros, scales, g_idx, temp_dq) = args
            return original_make_q_matrix(
                qweight,
                q_perm,
                q_invperm,
                q_scale,
                q_scale_max,
                q_groups,
                none_tensor,
                qzeros,
                scales,
                g_idx,
                none_tensor,
                temp_dq,
                0,
            )
        raise TypeError(f"make_q_matrix expects 10 or 13 args, got {len(args)}")

    shim = types.ModuleType("exllamav2_kernels")
    shim.make_q_matrix = make_q_matrix_compat
    shim.gemm_half_q_half = ext_c.gemm_half_q_half
    sys.modules["exllamav2_kernels"] = shim

    logger.info("exllamav2 kernel shim registered — auto_gptq will use exllamav2 CUDA kernels")
    return True
