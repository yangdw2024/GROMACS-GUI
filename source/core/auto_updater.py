#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动更新机制 - 参考VS Code自动更新、Chrome更新机制
实现：版本检查、自动下载、静默安装、版本回滚
"""

import os
import sys
import json
import time
import hashlib
import threading
import shutil
import zipfile
import subprocess
import glob as glob_mod
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum


def _get_app_root() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent.parent


class UpdateStatus(Enum):
    IDLE = "idle"
    CHECKING = "checking"
    UPDATING = "updating"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_UPDATE = "no_update"


class UpdateChannel(Enum):
    STABLE = "stable"
    BETA = "beta"
    DEV = "dev"


@dataclass
class FileManifest:
    path: str
    sha256: str
    size: int
    file_type: str


@dataclass
class VersionInfo:
    version: str
    channel: str
    release_date: str
    changelog: List[str]
    download_url: str
    checksum: str = ""
    file_size: int = 0


@dataclass
class UpdateResult:
    status: UpdateStatus
    current_version: str
    latest_version: Optional[str] = None
    message: str = ""
    changelog: List[str] = None
    progress: float = 0.0

    def __post_init__(self):
        if self.changelog is None:
            self.changelog = []

    @property
    def update_available(self) -> bool:
        return self.status == UpdateStatus.UPDATING

    def __getitem__(self, key):
        return getattr(self, key)


class AutoUpdater:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def _load_version_from_config(self) -> str:
        try:
            base_dir = _get_app_root()
            config_path = base_dir / "version.config"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    return config.get("version_string", "")
        except Exception:
            pass
        return ""

    def __init__(self):
        if self._initialized:
            return

        self._current_version = self._load_version_from_config()
        self._channel = UpdateChannel.STABLE
        self._update_status = UpdateStatus.IDLE
        self._progress = 0.0
        self._lock = threading.Lock()
        self._listeners: List[callable] = []

        self._config_dir = _get_app_root() / "config"
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._update_cache_dir = self._config_dir / "update_cache"
        self._update_cache_dir.mkdir(exist_ok=True)

        self._version_file = self._config_dir / "version_info.json"
        self._backup_dir = self._config_dir / "backup"

        self._initialized = True

    @property
    def current_version(self) -> str:
        return self._current_version

    @property
    def update_status(self) -> UpdateStatus:
        return self._update_status

    @property
    def progress(self) -> float:
        return self._progress

    def add_listener(self, callback: callable):
        self._listeners.append(callback)

    def remove_listener(self, callback: callable):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self, status: UpdateStatus, progress: float = 0.0, message: str = ""):
        self._update_status = status
        self._progress = progress
        for callback in self._listeners:
            try:
                callback(status, progress, message)
            except Exception:
                pass

    def check_for_update(self, channel: UpdateChannel = None) -> UpdateResult:
        channel = channel or self._channel
        self._notify(UpdateStatus.CHECKING, 0, "正在检查更新...")

        try:
            latest = self._get_latest_version(channel)
            if not latest:
                return UpdateResult(
                    status=UpdateStatus.FAILED,
                    current_version=self._current_version,
                    message="无法获取最新版本信息"
                )

            if self._compare_versions(self._current_version, latest.version) < 0:
                return UpdateResult(
                    status=UpdateStatus.UPDATING,
                    current_version=self._current_version,
                    latest_version=latest.version,
                    changelog=latest.changelog,
                    message=f"发现新版本: {latest.version}"
                )
            else:
                return UpdateResult(
                    status=UpdateStatus.NO_UPDATE,
                    current_version=self._current_version,
                    latest_version=latest.version,
                    message="当前已是最新版本"
                )
        except Exception as e:
            return UpdateResult(
                status=UpdateStatus.FAILED,
                current_version=self._current_version,
                message=f"检查更新失败: {e}"
            )

    def _get_latest_version(self, channel: UpdateChannel) -> Optional[VersionInfo]:
        try:
            local_version_file = self._config_dir / "latest_version.json"
            if local_version_file.exists():
                with open(local_version_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("channel") == channel.value:
                    return VersionInfo(
                        version=data["version"],
                        channel=data["channel"],
                        release_date=data.get("release_date", ""),
                        changelog=data.get("changelog", []),
                        download_url=data.get("download_url", ""),
                        checksum=data.get("checksum", ""),
                        file_size=data.get("file_size", 0),
                    )

            return VersionInfo(
                version=self._current_version,
                channel=channel.value,
                release_date="",
                changelog=[],
                download_url="",
            )
        except Exception:
            return None

    def _compare_versions(self, v1: str, v2: str) -> int:
        parts1 = [int(p) for p in v1.split(".") if p.isdigit()]
        parts2 = [int(p) for p in v2.split(".") if p.isdigit()]

        for p1, p2 in zip(parts1, parts2):
            if p1 < p2:
                return -1
            elif p1 > p2:
                return 1

        if len(parts1) < len(parts2):
            return -1
        elif len(parts1) > len(parts2):
            return 1
        return 0

    def download_update(self, download_url: str) -> bool:
        self._notify(UpdateStatus.UPDATING, 10, "开始下载更新...")

        try:
            filename = download_url.split("/")[-1] if download_url else "update.zip"
            filepath = self._update_cache_dir / filename

            if download_url.startswith("http"):
                try:
                    import urllib.request
                    with urllib.request.urlopen(download_url, timeout=60) as response:
                        total_size = int(response.headers.get("Content-Length", 0))
                        downloaded = 0
                        with open(filepath, "wb") as f:
                            chunk_size = 8192
                            while True:
                                chunk = response.read(chunk_size)
                                if not chunk:
                                    break
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0:
                                    progress = 10 + (downloaded / total_size) * 50
                                    self._notify(UpdateStatus.UPDATING, progress,
                                                f"下载中: {downloaded}/{total_size}")
                except Exception as e:
                    self._notify(UpdateStatus.FAILED, 0, f"下载失败: {e}")
                    return False
            else:
                shutil.copy2(download_url, filepath)
                self._notify(UpdateStatus.UPDATING, 60, "更新包已复制")

            return self._install_update(filepath)

        except Exception as e:
            self._notify(UpdateStatus.FAILED, 0, f"下载更新失败: {e}")
            return False

    def _install_update(self, update_file: Path) -> bool:
        self._notify(UpdateStatus.UPDATING, 65, "开始安装更新...")
        backup_root = Path()

        try:
            if update_file.suffix != ".zip":
                self._notify(UpdateStatus.FAILED, 0, "不支持的更新包格式")
                return False

            extract_dir = self._update_cache_dir / "extracted"
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            extract_dir.mkdir(exist_ok=True)

            with zipfile.ZipFile(update_file, "r") as zip_ref:
                zip_ref.extractall(extract_dir)
            self._notify(UpdateStatus.UPDATING, 72, "更新包已解压")

            update_type = self._determine_update_type(extract_dir)
            self._notify(UpdateStatus.UPDATING, 75, f"更新类型: {'全量' if update_type == 'full' else '增量'}")

            ok, backup_root = self._create_backup()
            if not ok:
                self._notify(UpdateStatus.FAILED, 0, "备份失败，终止更新")
                return False
            self._notify(UpdateStatus.UPDATING, 80, "备份完成")

            if not self._verify_update_package(extract_dir):
                self._restore_backup(backup_root)
                return False
            self._notify(UpdateStatus.UPDATING, 85, "更新包校验通过")

            if not self._apply_update(extract_dir, update_type):
                self._restore_backup(backup_root)
                self._notify(UpdateStatus.FAILED, 0, "应用更新失败，已回滚")
                return False
            self._notify(UpdateStatus.UPDATING, 92, "文件已更新")

            expected_version = self._read_version_from_extract_dir(extract_dir)
            if expected_version and not self._validate_version_consistency(expected_version):
                self._restore_backup(backup_root)
                self._notify(UpdateStatus.FAILED, 0, "版本号校验失败，已回滚")
                return False
            self._notify(UpdateStatus.UPDATING, 96, "版本号一致")

            self._update_version_info(extract_dir)
            self._notify(UpdateStatus.COMPLETED, 100, f"更新完成，新版本: {self._current_version}")
            return True

        except Exception as e:
            self._notify(UpdateStatus.FAILED, 0, f"安装更新失败: {e}")
            if backup_root.exists():
                self._restore_backup(backup_root)
            return False

    def _read_version_from_extract_dir(self, extract_dir: Path) -> str:
        config_path = extract_dir / "version.config"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("version_string", "")
            except Exception:
                pass
        return ""

    def _get_core_manifest_patterns(self) -> List[str]:
        if getattr(sys, 'frozen', False):
            return [
                "*.exe",
                "version.config",
                "config/**/*",
                "resources/**/*",
                "启动程序.bat",
                "说明书.md",
            ]
        else:
            return [
                "source/gromacs_gui_v4.py",
                "source/core/**/*.py",
                "source/core/**/*.json",
                "version.config",
                "config/**/*",
                "resources/**/*",
                "启动程序.bat",
                "说明书.md",
            ]

    @staticmethod
    def _calc_sha256(filepath: Path) -> str:
        h = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return ""

    def _generate_manifest(self, base_dir: Path) -> Dict[str, FileManifest]:
        manifest: Dict[str, FileManifest] = {}
        patterns = self._get_core_manifest_patterns()
        for pattern in patterns:
            for p in base_dir.glob(pattern):
                if not p.is_file():
                    continue
                rel = str(p.relative_to(base_dir)).replace("\\", "/")
                ftype = "core"
                if rel.startswith("config/"):
                    ftype = "config"
                elif rel.startswith("resources/"):
                    ftype = "resource"
                elif rel.endswith(".md") or rel.endswith(".txt"):
                    ftype = "doc"
                elif rel == "version.config":
                    ftype = "config"
                manifest[rel] = FileManifest(
                    path=rel,
                    sha256=self._calc_sha256(p),
                    size=p.stat().st_size,
                    file_type=ftype,
                )
        return manifest

    def _determine_update_type(self, extract_dir: Path) -> str:
        has_core = False
        for pattern in ["*.exe", "source/**/*.py"]:
            if list(extract_dir.glob(pattern)):
                has_core = True
                break
        return "full" if has_core else "incremental"

    def _create_backup(self) -> Tuple[bool, Path]:
        try:
            backup_id = f"backup_{int(time.time())}"
            backup_root = self._backup_dir / backup_id
            backup_root.mkdir(parents=True, exist_ok=True)
            app_root = _get_app_root()
            manifest = self._generate_manifest(app_root)
            manifest_path = backup_root / "manifest.json"
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump({k: asdict(v) for k, v in manifest.items()}, f, indent=2, ensure_ascii=False)
            for rel, info in manifest.items():
                src = app_root / rel
                dst = backup_root / rel
                if src.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
            return True, backup_root
        except Exception as e:
            self._notify(UpdateStatus.FAILED, 0, f"备份失败: {e}")
            return False, Path()

    def _restore_backup(self, backup_root: Path = None) -> bool:
        try:
            if backup_root is None or not backup_root.exists():
                backups = sorted(
                    [d for d in self._backup_dir.iterdir() if d.is_dir()],
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if not backups:
                    return False
                backup_root = backups[0]
            manifest_path = backup_root / "manifest.json"
            if not manifest_path.exists():
                return False
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            app_root = _get_app_root()
            for rel in manifest:
                src = backup_root / rel
                dst = app_root / rel
                if src.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
            self._notify(UpdateStatus.IDLE, 0, "已回滚到旧版本")
            return True
        except Exception:
            return False

    def _verify_update_package(self, extract_dir: Path) -> bool:
        expected_manifest_file = extract_dir / "update_manifest.json"
        if expected_manifest_file.exists():
            try:
                with open(expected_manifest_file, "r", encoding="utf-8") as f:
                    expected = json.load(f)
                for rel, info in expected.items():
                    actual_path = extract_dir / rel
                    if not actual_path.exists():
                        self._notify(UpdateStatus.FAILED, 0, f"更新包缺失文件: {rel}")
                        return False
                    actual_hash = self._calc_sha256(actual_path)
                    if actual_hash != info.get("sha256", ""):
                        self._notify(UpdateStatus.FAILED, 0, f"更新包文件哈希不匹配: {rel}")
                        return False
            except Exception as e:
                self._notify(UpdateStatus.FAILED, 0, f"校验更新包失败: {e}")
                return False
        return True

    def _apply_update(self, extract_dir: Path, update_type: str) -> bool:
        app_root = _get_app_root()
        patterns = self._get_core_manifest_patterns()
        updated = 0
        for pattern in patterns:
            for src in extract_dir.glob(pattern):
                if not src.is_file():
                    continue
                rel = str(src.relative_to(extract_dir)).replace("\\", "/")
                dst = app_root / rel
                if update_type == "incremental" and dst.exists():
                    old_hash = self._calc_sha256(dst)
                    new_hash = self._calc_sha256(src)
                    if old_hash == new_hash:
                        continue
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                updated += 1
        return updated > 0

    def _validate_version_consistency(self, expected_version: str) -> bool:
        try:
            app_root = _get_app_root()
            config_path = app_root / "version.config"
            if not config_path.exists():
                return False
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            actual = data.get("version_string", "")
            return actual == expected_version
        except Exception:
            return False

    def _update_version_info(self, extract_dir: Path):
        try:
            app_root = _get_app_root()
            config_path = app_root / "version.config"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._current_version = data.get("version_string", self._current_version)
                with open(self._version_file, "w", encoding="utf-8") as f:
                    json.dump({"version": self._current_version}, f)
        except Exception:
            pass

    def update_version_info(self, version: str, changelog: List[str] = None):
        changelog = changelog or []
        data = {
            "version": version,
            "channel": self._channel.value,
            "release_date": time.strftime("%Y-%m-%d"),
            "changelog": changelog,
        }
        with open(self._config_dir / "latest_version.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def set_current_version(self, version: str):
        self._current_version = version
        with open(self._version_file, "w", encoding="utf-8") as f:
            json.dump({"version": version}, f)

    def get_version_history(self) -> List[Dict]:
        history = []
        try:
            if self._version_file.exists():
                with open(self._version_file, "r", encoding="utf-8") as f:
                    history.append(json.load(f))
        except Exception:
            pass
        return history

    def generate_update_package(self, source_dir: str = None, output_dir: str = None,
                                 old_manifest_path: str = None, force_full: bool = False) -> Tuple[str, int, Dict]:
        """生成更新包（增量/全量自动判定）

        Args:
            source_dir: 新版本源目录，默认为当前项目根目录
            output_dir: 输出目录，默认为config/update_packages/
            old_manifest_path: 旧版本manifest.json路径，用于增量对比
            force_full: 强制全量打包

        Returns:
            (package_path, package_size_bytes, info_dict)
            info_dict包含: type(full/incremental), total_files, changed_files, size_reduction_pct
        """
        source = Path(source_dir) if source_dir else _get_app_root()
        if output_dir is None:
            output_dir = self._config_dir / "update_packages"
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)

        # 生成新版本manifest
        new_manifest = self._generate_manifest(source)
        if not new_manifest:
            return "", 0, {"error": "源目录无有效文件"}

        # 读取旧manifest
        old_manifest = {}
        if old_manifest_path and not force_full:
            old_path = Path(old_manifest_path)
            if old_path.exists():
                try:
                    with open(old_path, "r", encoding="utf-8") as f:
                        old_data = json.load(f)
                    for rel, info in old_data.items():
                        old_manifest[rel] = info.get("sha256", "")
                except Exception:
                    pass

        # 基于哈希对比判定变更文件
        changed_files = {}
        for rel, finfo in new_manifest.items():
            old_hash = old_manifest.get(rel, "")
            if old_hash != finfo.sha256:
                changed_files[rel] = finfo

        # 判定更新类型
        core_changed = any(f.file_type == "core" for f in changed_files.values())
        if force_full or core_changed or not old_manifest:
            update_type = "full"
            files_to_pack = new_manifest
        else:
            update_type = "incremental"
            files_to_pack = changed_files

        # 计算全量大小（用于对比）
        full_size = sum(info.size for info in new_manifest.values())

        # 打包
        version = self._current_version or "unknown"
        pkg_name = f"update_{update_type}_{version}_{int(time.time())}.zip"
        pkg_path = output / pkg_name

        with zipfile.ZipFile(str(pkg_path), 'w', zipfile.ZIP_DEFLATED) as zf:
            # 写入变更文件
            for rel, finfo in files_to_pack.items():
                src = source / rel
                if src.exists():
                    zf.write(str(src), rel)

            # 写入update_manifest.json
            manifest_data = {rel: asdict(finfo) for rel, finfo in files_to_pack.items()}
            manifest_data["__update_info__"] = {
                "type": update_type,
                "version": version,
                "total_files": len(new_manifest),
                "changed_files": len(changed_files),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            zf.writestr("update_manifest.json", json.dumps(manifest_data, indent=2, ensure_ascii=False))

        pkg_size = pkg_path.stat().st_size
        # 生成全量包用于体积对比
        full_pkg_name = f"update_full_{version}_{int(time.time())}.zip"
        full_pkg_path = output / full_pkg_name
        with zipfile.ZipFile(str(full_pkg_path), 'w', zipfile.ZIP_DEFLATED) as zf:
            for rel, finfo in new_manifest.items():
                src = source / rel
                if src.exists():
                    zf.write(str(src), rel)
            full_manifest_data = {rel: asdict(finfo) for rel, finfo in new_manifest.items()}
            full_manifest_data["__update_info__"] = {
                "type": "full",
                "version": version,
                "total_files": len(new_manifest),
                "changed_files": len(changed_files),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            zf.writestr("update_manifest.json", json.dumps(full_manifest_data, indent=2, ensure_ascii=False))
        full_pkg_size = full_pkg_path.stat().st_size

        size_reduction = round((1 - pkg_size / full_pkg_size) * 100, 1) if full_pkg_size > 0 else 0

        info = {
            "type": update_type,
            "package_path": str(pkg_path),
            "package_size_bytes": pkg_size,
            "total_files": len(new_manifest),
            "changed_files": len(changed_files),
            "full_size_bytes": full_size,
            "full_package_size_bytes": full_pkg_size,
            "size_reduction_pct": size_reduction,
            "core_changed": core_changed,
        }

        return str(pkg_path), pkg_size, info

    def run_update(self, download_url: str = "") -> UpdateResult:
        check_result = self.check_for_update()

        if check_result.status == UpdateStatus.NO_UPDATE:
            return check_result

        if check_result.status == UpdateStatus.UPDATING:
            if download_url:
                success = self.download_update(download_url)
                if success:
                    return UpdateResult(
                        status=UpdateStatus.COMPLETED,
                        current_version=self._current_version,
                        latest_version=check_result.latest_version,
                        changelog=check_result.changelog,
                        message="更新完成，请重启程序"
                    )
                else:
                    return UpdateResult(
                        status=UpdateStatus.FAILED,
                        current_version=self._current_version,
                        latest_version=check_result.latest_version,
                        message="更新失败"
                    )
            else:
                return check_result

        return check_result
