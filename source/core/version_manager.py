#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GROMACS版本管理器 - 重构版本扫描、去重、过滤、清理
功能：版本去重、无效版本过滤、PLUMED精细化校验、版本元数据管理
"""

import os
import sys
import re
import json
import hashlib
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, asdict, field
from enum import Enum


def _get_app_root() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent.parent

from .logger import AppLogger


class PlumedStatus(Enum):
    NOT_SUPPORTED = "not_supported"
    SUPPORTED = "supported"
    BROKEN_LIBRARY = "broken_library"
    MISSING_FILES = "missing_files"
    UNKNOWN = "unknown"


class VersionValidity(Enum):
    VALID = "valid"
    INVALID_EXE = "invalid_exe"
    MISSING_FORCEFIELD = "missing_forcefield"
    MISSING_CUDA = "missing_cuda"
    BROKEN_DEPENDENCY = "broken_dependency"
    BUILD_ARTIFACT = "build_artifact"
    UNKNOWN = "unknown"


@dataclass
class VersionMetadata:
    name: str = ""
    path: str = ""
    gmx_exe: str = ""
    version: str = ""
    precision: str = ""
    simd: str = ""
    gpu: str = ""
    plumed: str = ""
    plumed_status: str = PlumedStatus.UNKNOWN.value
    plumed_detail: str = ""
    valid: bool = False
    validity_status: str = VersionValidity.UNKNOWN.value
    validity_detail: str = ""
    size_mb: float = 0.0
    last_modified: str = ""
    mtime: float = 0.0
    score: int = 0
    build_params: Dict[str, str] = field(default_factory=dict)
    hash_id: str = ""
    duplicate_of: str = ""  # 如果是重复版本，指向主版本名称
    is_duplicate: bool = False
    is_build_artifact: bool = False

    def to_dict(self) -> Dict:
        return asdict(self)

    @property
    def display_name(self) -> str:
        if self.is_duplicate:
            return f"{self.name} (重复)"
        return self.name


class VersionManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._versions: Dict[str, VersionMetadata] = {}
        self._selected_version: Optional[str] = None
        self._logger = AppLogger()
        self._initialized = True

    def scan_versions(self, base_dir: str = None,
                      filter_invalid: bool = False,
                      deduplicate: bool = False) -> Dict[str, VersionMetadata]:
        """扫描GROMACS版本，支持过滤和去重"""
        if base_dir is None:
            app_root = _get_app_root()
            candidates = [
                app_root / "gromacs",
                app_root.parent / "gromacs",
                app_root.parent.parent / "gromacs",
            ]
            # 开发环境兜底路径（仅在开发机上生效）
            dev_path = Path(r"D:\YDW\Trae_Gromacs\gromacs")
            if dev_path.exists():
                candidates.append(dev_path)
            
            for cand in candidates:
                if cand.exists() and cand.is_dir():
                    base_dir = cand
                    break
            if base_dir is None:
                base_dir = candidates[0]

        base_path = Path(base_dir)
        if not base_path.exists():
            self._logger.warning(f"GROMACS目录不存在: {base_path}")
            return {}

        raw_versions = {}

        # 检查base_path是否直接包含bin/gmx.exe（便携包模式，没有子版本目录）
        direct_gmx = base_path / "bin" / "gmx.exe"
        if direct_gmx.exists():
            version_name = base_path.name
            meta = self._analyze_version(version_name, str(base_path), str(direct_gmx))
            raw_versions[version_name] = meta
        else:
            # 标准模式：base_path下有多个版本子目录
            for item in sorted(base_path.iterdir()):
                if not item.is_dir():
                    continue
                if item.name.startswith("build-"):
                    continue

                gmx_exe = item / "bin" / "gmx.exe"
                if not gmx_exe.exists():
                    continue

                meta = self._analyze_version(item.name, str(item), str(gmx_exe))
                raw_versions[item.name] = meta

        self._logger.info(f"原始扫描: 发现 {len(raw_versions)} 个版本")

        # 步骤1: 标记编译产物和无效版本
        self._validate_all(raw_versions)

        # 步骤2: 去重
        if deduplicate:
            raw_versions = self._deduplicate_versions(raw_versions)

        # 步骤3: 过滤无效版本
        if filter_invalid:
            valid_versions = {}
            for name, meta in raw_versions.items():
                if meta.valid and not meta.is_duplicate and not meta.is_build_artifact:
                    valid_versions[name] = meta
            raw_versions = valid_versions

        self._versions = raw_versions
        self._logger.info(f"最终有效版本: {len(raw_versions)} 个")
        return raw_versions

    def _analyze_version(self, name: str, path: str, gmx_exe: str) -> VersionMetadata:
        """分析单个版本"""
        meta = VersionMetadata()
        meta.name = name
        meta.path = path
        meta.gmx_exe = gmx_exe
        mtime_val = Path(path).stat().st_mtime
        meta.last_modified = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(mtime_val)
        )
        meta.mtime = mtime_val
        meta.size_mb = round(self._get_dir_size(Path(path)) / (1024 * 1024), 1)

        # 解析构建参数
        meta.build_params = self._parse_build_params(name)

        # 执行gmx --version获取信息
        info = self._get_version_info(gmx_exe)
        meta.version = info.get("version", "")
        meta.precision = info.get("precision", "")
        meta.simd = info.get("simd", "")
        meta.gpu = info.get("gpu", "")
        meta.plumed = info.get("plumed", "")

        # 计算唯一标识：gmx.exe哈希 + SIMD + GPU + PLUMED
        meta.hash_id = self._compute_version_hash(path, meta)

        return meta

    def _parse_build_params(self, name: str) -> Dict[str, str]:
        """从版本名称解析构建参数"""
        params = {}
        name_lower = name.lower()

        # 版本号
        ver_match = re.search(r'(\d{4}\.\d)', name_lower)
        if ver_match:
            params["gromacs_version"] = ver_match.group(1)

        # SIMD
        if "avx512" in name_lower or "avx-512" in name_lower:
            params["simd"] = "AVX-512"
        elif "avx2" in name_lower:
            params["simd"] = "AVX2"
        elif "sse" in name_lower:
            params["simd"] = "SSE"

        # GPU
        if "cuda" in name_lower:
            params["gpu"] = "CUDA"
        elif "opencl" in name_lower:
            params["gpu"] = "OpenCL"

        # PLUMED
        if "plumed" in name_lower:
            params["plumed"] = "yes"

        # sm_120
        if "sm120" in name_lower:
            params["cuda_arch"] = "sm_120"

        return params

    def _compute_version_hash(self, path: str, meta: VersionMetadata = None) -> str:
        """计算版本唯一标识：gmx.exe文件哈希 + SIMD + GPU + PLUMED"""
        try:
            key_parts = []
            p = Path(path)

            # 1. gmx.exe SHA256前16位
            gmx = p / "bin" / "gmx.exe"
            if gmx.exists():
                h = hashlib.sha256(gmx.read_bytes()).hexdigest()[:16]
                key_parts.append(h)

            # 2. SIMD指令集
            # 3. GPU支持状态
            # 4. PLUMED支持状态
            if meta:
                key_parts.append(meta.simd)
                key_parts.append(meta.gpu)
                key_parts.append(meta.plumed)

            return hashlib.md5("|".join(key_parts).encode()).hexdigest()[:16]
        except Exception:
            return ""

    def _validate_all(self, versions: Dict[str, VersionMetadata]):
        """校验所有版本的有效性"""
        for name, meta in versions.items():
            self._validate_version(meta)

    def _validate_version(self, meta: VersionMetadata):
        """校验单个版本"""
        path = Path(meta.path)
        gmx_exe = Path(meta.gmx_exe)

        # 检查1: gmx.exe是否存在且可执行
        if not gmx_exe.exists():
            meta.valid = False
            meta.validity_status = VersionValidity.INVALID_EXE.value
            meta.validity_detail = "gmx.exe不存在"
            return

        if gmx_exe.stat().st_size == 0:
            meta.valid = False
            meta.validity_status = VersionValidity.INVALID_EXE.value
            meta.validity_detail = "gmx.exe为空文件"
            return

        # 检查2: 执行gmx --version
        try:
            startupinfo = None
            if sys.platform.startswith("win"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(
                [str(gmx_exe), "--version"],
                capture_output=True, text=True, timeout=15,
                startupinfo=startupinfo
            )
            if result.returncode != 0:
                meta.valid = False
                meta.validity_status = VersionValidity.INVALID_EXE.value
                meta.validity_detail = f"gmx.exe执行失败: {result.stderr[:100]}"
                return
        except Exception as e:
            meta.valid = False
            meta.validity_status = VersionValidity.INVALID_EXE.value
            meta.validity_detail = f"gmx.exe执行异常: {e}"
            return

        # 检查3: 力场目录完整性（必须有实际.ff子目录）
        ff_dir = path / "share" / "gromacs" / "top"
        if not ff_dir.exists():
            meta.valid = False
            meta.validity_status = VersionValidity.MISSING_FORCEFIELD.value
            meta.validity_detail = "力场目录不存在"
            return
        ff_subdirs = [d for d in ff_dir.iterdir() if d.is_dir() and d.suffix == ".ff"]
        if not ff_subdirs:
            meta.valid = False
            meta.validity_status = VersionValidity.MISSING_FORCEFIELD.value
            meta.validity_detail = "力场文件缺失（无.ff子目录）"
            return

        # 检查4: PLUMED精细化校验
        self._validate_plumed_detailed(meta)
        # 如果PLUMED文件损坏，标记为无效
        if meta.plumed_status == PlumedStatus.BROKEN_LIBRARY.value:
            meta.valid = False
            meta.validity_status = VersionValidity.BROKEN_DEPENDENCY.value
            meta.validity_detail = meta.plumed_detail
            return

        # 检查5: CUDA核心依赖完整性（如果声称支持GPU）
        if "cuda" in meta.gpu.lower():
            cuda_ok = False
            for cudart in [path / "bin" / "cudart64_13.dll", path / "bin" / "cudart64_12.dll", path / "bin" / "cudart64_11.dll"]:
                if cudart.exists() and cudart.stat().st_size > 0:
                    cuda_ok = True
                    break
            if not cuda_ok:
                meta.valid = False
                meta.validity_status = VersionValidity.MISSING_CUDA.value
                meta.validity_detail = "CUDA运行时库缺失或损坏"
                return
            # 额外检查 cufft（PME必需）
            cufft_ok = False
            for cufft in [path / "bin" / "cufft64_12.dll", path / "bin" / "cufft64_11.dll", path / "bin" / "cufft64_10.dll"]:
                if cufft.exists() and cufft.stat().st_size > 0:
                    cufft_ok = True
                    break
            if not cufft_ok:
                meta.valid = False
                meta.validity_status = VersionValidity.MISSING_CUDA.value
                meta.validity_detail = "CUDA FFT库缺失或损坏"
                return

        # 检查6: 核心依赖DLL完整性（Windows通用）
        bin_dir = path / "bin"
        # 检查gmx.exe本身是否完整（大小异常小可能为损坏）
        gmx_size = gmx_exe.stat().st_size
        if gmx_size < 1024 * 1024:  # 小于1MB几乎不可能为正常gmx.exe
            meta.valid = False
            meta.validity_status = VersionValidity.INVALID_EXE.value
            meta.validity_detail = f"gmx.exe异常过小({gmx_size}字节)，可能编译失败"
            return

        # 全部通过
        meta.valid = True
        meta.validity_status = VersionValidity.VALID.value
        meta.validity_detail = "版本有效"

    def _validate_plumed_detailed(self, meta: VersionMetadata):
        """精细化PLUMED校验，区分三种场景"""
        path = Path(meta.path)
        bin_dir = path / "bin"

        # 检查PLUMED是否声称支持
        claims_plumed = meta.plumed.lower() in ("yes", "enabled", "是", "true")
        name_has_plumed = "plumed" in meta.name.lower()

        if not claims_plumed and not name_has_plumed:
            meta.plumed_status = PlumedStatus.NOT_SUPPORTED.value
            meta.plumed_detail = "此版本不支持PLUMED"
            return

        # 声称支持，检查文件
        kernel = bin_dir / "libplumedKernel.dll"

        # 动态链接PLUMED：检查libplumedKernel.dll
        if kernel.exists():
            try:
                size = kernel.stat().st_size
                if size == 0:
                    meta.plumed_status = PlumedStatus.BROKEN_LIBRARY.value
                    meta.plumed_detail = "PLUMED库文件为空"
                    meta.plumed = "broken (empty)"
                    return
            except Exception as e:
                meta.plumed_status = PlumedStatus.BROKEN_LIBRARY.value
                meta.plumed_detail = f"PLUMED库文件不可读: {e}"
                meta.plumed = "broken (unreadable)"
                return

            meta.plumed_status = PlumedStatus.SUPPORTED.value
            meta.plumed_detail = "PLUMED支持完整（动态链接）"
            meta.plumed = "enabled"
            return

        # 静态链接PLUMED：libplumedKernel.dll不存在，但gmx.exe可能已静态链接PLUMED
        # 通过运行gmx mdrun -h检查是否支持-plumed参数
        gmx_exe = bin_dir / "gmx.exe"
        if gmx_exe.exists():
            try:
                import subprocess
                result = subprocess.run(
                    [str(gmx_exe), "mdrun", "-h"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                output = result.stdout + result.stderr
                if "-plumed" in output or "plumed.dat" in output:
                    meta.plumed_status = PlumedStatus.SUPPORTED.value
                    meta.plumed_detail = "PLUMED支持完整（静态链接）"
                    meta.plumed = "enabled"
                    return
            except Exception:
                pass

        # 确实不支持
        if claims_plumed:
            meta.plumed_status = PlumedStatus.MISSING_FILES.value
            meta.plumed_detail = "PLUMED文件缺失: libplumedKernel.dll"
            meta.plumed = "missing (libplumedKernel.dll)"
        else:
            meta.plumed_status = PlumedStatus.NOT_SUPPORTED.value
            meta.plumed_detail = "未声明PLUMED支持"
        return

    def _deduplicate_versions(self, versions: Dict[str, VersionMetadata]) -> Dict[str, VersionMetadata]:
        """去重：识别同源重复编译产物 + 智能名称去重（白名单版本强制保留）"""
        # 读取白名单
        whitelist = self._load_version_whitelist()

        # 步骤1: 基于文件哈希去重
        hash_map: Dict[str, str] = {}  # hash -> first version name
        duplicates = []

        for name, meta in versions.items():
            if not meta.hash_id:
                continue
            if name in whitelist:
                # 白名单版本：如果hash冲突，不标记为重复，独立保留
                if meta.hash_id not in hash_map:
                    hash_map[meta.hash_id] = name
                continue
            if meta.hash_id in hash_map:
                original = hash_map[meta.hash_id]
                meta.is_duplicate = True
                meta.duplicate_of = original
                duplicates.append(name)
                self._logger.info(
                    f"版本去重: '{name}' 与 '{original}' 为同源重复编译产物"
                )
            else:
                hash_map[meta.hash_id] = name

        # 步骤2: 基于名称前缀智能去重
        # 提取名称前缀（去掉 -final, -v2, -v3, -test 等后缀）
        prefix_groups: Dict[str, List[Tuple[str, VersionMetadata]]] = {}

        for name, meta in versions.items():
            if meta.is_duplicate:
                continue
            if name in whitelist:
                continue  # 白名单版本不参与名称前缀去重
            prefix = self._extract_name_prefix(name)
            if prefix not in prefix_groups:
                prefix_groups[prefix] = []
            prefix_groups[prefix].append((name, meta))

        # 对每个前缀组，只保留最佳版本
        for prefix, group in prefix_groups.items():
            if len(group) <= 1:
                continue

            # 评分选择最佳版本（保留最新、最完整、最稳定的）
            def score_version(item):
                name, meta = item
                s = 0
                # 文件最新加分（越高越新，权重最大）
                s += int(meta.mtime) / 3600  # 每小时1分
                # 名称越短越可能是主版本
                s -= len(name) * 10
                # PLUMED完整支持加分
                if meta.plumed_status == PlumedStatus.SUPPORTED.value:
                    s += 500
                # 有效版本加分
                if meta.valid:
                    s += 300
                # 文件大小适中（过大可能是调试版本）
                if 50 < meta.size_mb < 500:
                    s += 100
                # 名称包含 -fixed 加分
                if "fixed" in name.lower():
                    s += 200
                # 名称包含 -final 加分
                if "final" in name.lower():
                    s += 100
                return s

            group_sorted = sorted(group, key=score_version, reverse=True)
            best_name, best_meta = group_sorted[0]

            for name, meta in group_sorted[1:]:
                meta.is_duplicate = True
                meta.duplicate_of = best_name
                duplicates.append(name)
                self._logger.info(
                    f"版本去重: '{name}' 与 '{best_name}' 为同名前缀重复版本，"
                    f"已标记为重复"
                )

        if duplicates:
            self._logger.info(f"去重完成: 共标记 {len(duplicates)} 个重复版本")

        return versions

    def _load_version_whitelist(self) -> set:
        """从version.config读取版本白名单"""
        try:
            config_path = _get_app_root() / "version.config"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return set(data.get("version_whitelist", []))
        except Exception:
            pass
        return set()

    def _save_version_whitelist(self, whitelist: list):
        """保存版本白名单到version.config"""
        try:
            config_path = _get_app_root() / "version.config"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["version_whitelist"] = whitelist
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                self._logger.info(f"版本白名单已保存: {whitelist}")
        except Exception as e:
            self._logger.error(f"保存版本白名单失败: {e}")

    def get_version_whitelist(self) -> list:
        """获取当前版本白名单（公开接口）"""
        return sorted(self._load_version_whitelist())

    def update_version_whitelist(self, whitelist: list):
        """更新版本白名单并重新扫描版本（公开接口）"""
        self._save_version_whitelist(whitelist)

    def _extract_name_prefix(self, name: str) -> str:
        """提取版本名称前缀（去掉衍生后缀）"""
        import re
        # 去掉常见的衍生后缀
        suffixes = [
            r'-v\d+$', r'-final\d*$', r'-fixed\d*$', r'-test\d*$',
            r'-old\d*$', r'-backup\d*$', r'-copy\d*$', r'-\d+$'
        ]
        prefix = name
        for pattern in suffixes:
            prefix = re.sub(pattern, '', prefix, flags=re.IGNORECASE)
        return prefix

    def get_duplicate_versions(self) -> List[str]:
        """获取所有被标记为重复的版本名称"""
        return [name for name, meta in self._versions.items() if meta.is_duplicate]

    def get_invalid_versions(self) -> List[Tuple[str, str]]:
        """获取所有无效版本（名称, 原因）"""
        return [
            (name, meta.validity_detail)
            for name, meta in self._versions.items()
            if not meta.valid
        ]

    def get_plumed_broken_versions(self) -> List[Tuple[str, str]]:
        """获取PLUMED损坏的版本"""
        return [
            (name, meta.plumed_detail)
            for name, meta in self._versions.items()
            if meta.plumed_status in (PlumedStatus.BROKEN_LIBRARY.value, PlumedStatus.MISSING_FILES.value)
        ]

    def export_versions(self, version_names: List[str], export_dir: str) -> Tuple[int, List[str]]:
        """批量导出选中版本到外部压缩包，自动过滤临时编译垃圾文件"""
        import zipfile
        export_path = Path(export_dir)
        export_path.mkdir(parents=True, exist_ok=True)
        exported = 0
        errors = []

        # 临时编译垃圾文件模式
        junk_patterns = [
            "*.pyc", "__pycache__", "*.tmp", "*.bak",
            "CMakeFiles", "CMakeCache.txt", "cmake_install.cmake",
            "Makefile", "*.o", "*.obj", "*.lib", "*.exp", "*.pdb",
        ]

        for name in version_names:
            if name not in self._versions:
                errors.append(f"版本 {name} 不在扫描列表中")
                continue

            meta = self._versions[name]
            version_path = Path(meta.path)
            if not version_path.exists():
                errors.append(f"版本 {name} 目录不存在: {version_path}")
                continue

            zip_path = export_path / f"{name}.zip"
            try:
                with zipfile.ZipFile(str(zip_path), 'w', zipfile.ZIP_DEFLATED) as zf:
                    for file_path in version_path.rglob("*"):
                        if not file_path.is_file():
                            continue
                        rel = file_path.relative_to(version_path)
                        # 过滤临时编译垃圾文件
                        skip = False
                        for pat in junk_patterns:
                            if pat.startswith("*"):
                                if file_path.match(pat):
                                    skip = True
                                    break
                            elif pat in rel.parts or file_path.name == pat:
                                skip = True
                                break
                        if skip:
                            continue
                        zf.write(str(file_path), str(rel))

                size_mb = zip_path.stat().st_size / (1024 * 1024)
                self._logger.info(f"已导出版本 {name} -> {zip_path.name} ({size_mb:.1f} MB)")
                exported += 1
            except Exception as e:
                errors.append(f"导出 {name} 失败: {e}")
                if zip_path.exists():
                    zip_path.unlink()

        return exported, errors

    def import_versions(self, zip_paths: List[str], target_base_dir: str = None) -> Tuple[int, List[str]]:
        """批量导入外部版本压缩包，自动校验版本有效性，冲突版本返回提示"""
        import zipfile
        import tempfile

        if target_base_dir is None:
            # 默认导入到gromacs目录
            gromacs_dir = _get_app_root() / "gromacs"
            if not gromacs_dir.exists():
                gromacs_dir.mkdir(parents=True, exist_ok=True)
            target_base_dir = str(gromacs_dir)

        imported = 0
        conflicts = []

        for zip_path_str in zip_paths:
            zip_path = Path(zip_path_str)
            if not zip_path.exists():
                conflicts.append(f"文件不存在: {zip_path}")
                continue

            # 解压到临时目录先校验
            version_name = zip_path.stem
            target_dir = Path(target_base_dir) / version_name

            # 冲突检测
            if target_dir.exists():
                conflicts.append(f"版本 {version_name} 已存在，请先删除旧版本或更换目标目录")
                continue

            try:
                with zipfile.ZipFile(str(zip_path), 'r') as zf:
                    # 检查压缩包内是否包含有效的gmx.exe
                    names = zf.namelist()
                    has_gmx = any(n.endswith("bin/gmx.exe") or n.endswith("bin\\gmx.exe") for n in names)
                    if not has_gmx:
                        # 也检查根目录直接包含bin/gmx.exe的情况
                        has_gmx = any("gmx.exe" in n for n in names)
                    if not has_gmx:
                        conflicts.append(f"{version_name}: 压缩包内未找到gmx.exe，不是有效的GROMACS版本")
                        continue

                    # 解压到目标目录
                    zf.extractall(str(target_dir))

                    # 解压后检查：如果顶层有单层子目录，提升一层
                    top_items = list(target_dir.iterdir())
                    if len(top_items) == 1 and top_items[0].is_dir():
                        sub = top_items[0]
                        # 如果子目录名不是标准的bin/share结构，可能是打包时多了一层
                        if not (sub.name == "bin" or sub.name == "share"):
                            # 提升子目录内容到target_dir
                            temp_dir = target_dir.parent / f"_{version_name}_temp"
                            sub.rename(temp_dir)
                            for item in temp_dir.iterdir():
                                item.rename(target_dir / item.name)
                            temp_dir.rmdir()

                # 校验导入的版本
                gmx_exe = target_dir / "bin" / "gmx.exe"
                if not gmx_exe.exists():
                    conflicts.append(f"{version_name}: 解压后未找到bin/gmx.exe")
                    import shutil
                    shutil.rmtree(str(target_dir), ignore_errors=True)
                    continue

                # 执行版本分析校验
                meta = self._analyze_version(version_name, str(target_dir), str(gmx_exe))
                self._validate_version(meta)

                if not meta.valid:
                    # 无效版本仍然导入，但提示用户
                    conflicts.append(f"{version_name}: 导入成功但校验无效 - {meta.validity_detail}")

                # 加入扫描列表
                self._versions[version_name] = meta
                imported += 1
                self._logger.info(f"已导入版本 {version_name} (有效: {meta.valid})")

            except Exception as e:
                conflicts.append(f"导入 {version_name} 失败: {e}")
                if target_dir.exists():
                    import shutil
                    shutil.rmtree(str(target_dir), ignore_errors=True)

        return imported, conflicts

    def delete_version(self, name: str) -> Tuple[bool, str]:
        """删除指定版本目录"""
        if name not in self._versions:
            return False, f"版本 {name} 不存在"

        meta = self._versions[name]
        path = Path(meta.path)

        if not path.exists():
            return False, f"版本目录不存在: {path}"

        try:
            import shutil
            shutil.rmtree(path)
            del self._versions[name]
            self._logger.info(f"已删除版本: {name}")
            return True, f"版本 {name} 已删除"
        except Exception as e:
            return False, f"删除失败: {e}"

    def get_version_summary(self) -> Dict[str, Any]:
        """获取版本统计摘要"""
        total = len(self._versions)
        valid = sum(1 for m in self._versions.values() if m.valid)
        invalid = total - valid
        duplicates = sum(1 for m in self._versions.values() if m.is_duplicate)
        plumed_ok = sum(1 for m in self._versions.values() if m.plumed_status == PlumedStatus.SUPPORTED.value)
        gpu_ok = sum(1 for m in self._versions.values() if "cuda" in m.gpu.lower())

        return {
            "total": total,
            "valid": valid,
            "invalid": invalid,
            "duplicates": duplicates,
            "plumed_supported": plumed_ok,
            "gpu_supported": gpu_ok,
            "versions": {name: m.to_dict() for name, m in self._versions.items()}
        }

    def select_best_version(self, prefer_plumed: bool = False, prefer_gpu: bool = True) -> Optional[str]:
        """选择最佳版本"""
        valid_versions = {
            k: v for k, v in self._versions.items()
            if v.valid and not v.is_duplicate
        }

        if not valid_versions:
            return None

        def score(v: VersionMetadata) -> int:
            s = 0
            if prefer_gpu and "cuda" in v.gpu.lower():
                s += 1000
            simd = v.simd.lower()
            if "avx_512" in simd or "avx512" in simd:
                s += 500
            elif "avx2" in simd:
                s += 300
            if prefer_plumed and v.plumed_status == PlumedStatus.SUPPORTED.value:
                s += 100
            try:
                parts = v.version.split(".")
                major = int(parts[0]) if len(parts) > 0 else 0
                minor = int(parts[1]) if len(parts) > 1 else 0
                s += major * 10 + minor
            except Exception:
                pass
            return s

        best = max(valid_versions.items(), key=lambda x: score(x[1]))
        return best[0]

    def select_version(self, version_name: str) -> Tuple[bool, str]:
        """选择版本，返回(成功, 消息)"""
        if version_name not in self._versions:
            return False, f"版本 {version_name} 不存在"

        meta = self._versions[version_name]
        if meta.is_duplicate:
            return False, f"版本 {version_name} 是重复编译产物，请选择主版本: {meta.duplicate_of}"

        if not meta.valid:
            return False, f"版本 {version_name} 无效: {meta.validity_detail}"

        self._selected_version = version_name
        return True, f"已选择版本: {version_name}"

    def get_selected_version(self) -> Optional[VersionMetadata]:
        if self._selected_version and self._selected_version in self._versions:
            return self._versions[self._selected_version]
        best = self.select_best_version()
        if best:
            self._selected_version = best
            return self._versions[best]
        return None

    def get_gmx_exe(self) -> str:
        version = self.get_selected_version()
        if version:
            return version.gmx_exe
        raise RuntimeError("未找到可用的GROMACS版本")

    def get_version_list(self) -> List[Dict[str, Any]]:
        return [v.to_dict() for v in self._versions.values()]

    def get_valid_version_names(self) -> List[str]:
        return [
            name for name, meta in self._versions.items()
            if meta.valid and not meta.is_duplicate
        ]

    def _get_version_info(self, gmx_exe: str) -> Dict[str, str]:
        """执行gmx --version获取信息"""
        info = {}
        try:
            startupinfo = None
            if sys.platform.startswith("win"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(
                [gmx_exe, "--version"],
                capture_output=True, text=True, timeout=15,
                startupinfo=startupinfo
            )
            out = result.stdout + result.stderr

            for line in out.split("\n"):
                line_lower = line.lower()
                if "gromacs version:" in line_lower:
                    info["version"] = line.split(":", 1)[1].strip()
                elif "precision:" in line_lower:
                    info["precision"] = line.split(":", 1)[1].strip()
                elif "simd instructions:" in line_lower:
                    info["simd"] = line.split(":", 1)[1].strip()
                elif "gpu support:" in line_lower:
                    info["gpu"] = line.split(":", 1)[1].strip()
                elif "plumed support:" in line_lower:
                    info["plumed"] = line.split(":", 1)[1].strip()
        except Exception:
            pass
        return info

    def _get_dir_size(self, path: Path) -> int:
        total = 0
        try:
            for item in path.rglob("*"):
                if item.is_file():
                    try:
                        total += item.stat().st_size
                    except Exception:
                        pass
        except Exception:
            pass
        return total