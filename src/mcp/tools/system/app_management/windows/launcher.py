"""Windows系统应用程序启动器.

提供Windows平台下的应用程序启动功能。
所有 subprocess 调用均使用列表形式，不使用 shell=True。
"""

import base64
import os
import subprocess

from src.logging import get_logger

logger = get_logger()

# Windows 进程创建标志（仅在 Windows 上可用）
_DETACHED_PROCESS = 0x00000008


def launch_application(app_name: str) -> bool:
    """在Windows上启动应用程序.

    Args:
        app_name: 应用程序名称

    Returns:
        bool: 启动是否成功
    """
    try:
        logger.info(f"[WindowsLauncher] 启动应用程序: {app_name}")

        # 按优先级尝试不同的启动方法
        launch_methods = [
            ("PowerShell Start-Process", _try_powershell_start),
            ("os.startfile", _try_os_startfile),
            ("注册表查找", _try_registry_launch),
            ("常见路径", _try_common_paths),
            ("where命令", _try_where_command),
            ("UWP应用", _try_uwp_launch),
        ]

        for method_name, method_func in launch_methods:
            try:
                if method_func(app_name):
                    logger.info(f"[WindowsLauncher] {method_name}成功启动: {app_name}")
                    return True
                else:
                    logger.debug(f"[WindowsLauncher] {method_name}启动失败: {app_name}")
            except Exception as e:
                logger.debug(f"[WindowsLauncher] {method_name}异常: {e}")

        logger.warning(f"[WindowsLauncher] 所有Windows启动方法都失败了: {app_name}")
        return False

    except Exception as e:
        logger.error(f"[WindowsLauncher] Windows启动异常: {e}", exc_info=True)
        return False


def launch_uwp_app_by_path(uwp_path: str) -> bool:
    """通过UWP路径启动应用程序.

    Args:
        uwp_path: UWP应用程序路径（shell:AppsFolder\\...格式）

    Returns:
        bool: 启动是否成功
    """
    try:
        if uwp_path.startswith("shell:AppsFolder\\"):
            subprocess.Popen(
                ["explorer.exe", uwp_path],
                creationflags=_DETACHED_PROCESS,
            )
            logger.info(f"[WindowsLauncher] UWP应用启动成功: {uwp_path}")
            return True
        else:
            return False
    except Exception as e:
        logger.error(f"[WindowsLauncher] UWP应用启动失败: {e}")
        return False


def launch_shortcut(shortcut_path: str) -> bool:
    """启动快捷方式文件.

    Args:
        shortcut_path: 快捷方式文件路径

    Returns:
        bool: 启动是否成功
    """
    try:
        os.startfile(shortcut_path)
        logger.info(f"[WindowsLauncher] 快捷方式启动成功: {shortcut_path}")
        return True
    except Exception as e:
        logger.error(f"[WindowsLauncher] 快捷方式启动失败: {e}")
        return False


def _try_powershell_start(app_name: str) -> bool:
    """尝试使用 PowerShell Start-Process 启动应用程序."""
    try:
        result = subprocess.run(
            ["powershell", "-Command", "Start-Process", "-FilePath", app_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def _try_os_startfile(app_name: str) -> bool:
    """尝试使用os.startfile启动应用程序."""
    try:
        os.startfile(app_name)
        return True
    except OSError:
        return False


def _try_registry_launch(app_name: str) -> bool:
    """尝试通过注册表查找并启动应用程序."""
    try:
        executable_path = _find_executable_in_registry(app_name)
        if executable_path:
            subprocess.Popen(
                [executable_path],
                creationflags=_DETACHED_PROCESS,
            )
            return True
    except Exception as e:
        logger.debug(f"[WindowsLauncher] 注册表查找应用失败: {e}")
    return False


def _try_common_paths(app_name: str) -> bool:
    """尝试常见的应用程序路径."""
    username = os.getenv("USERNAME", "")
    common_paths = [
        f"C:\\Program Files\\{app_name}\\{app_name}.exe",
        f"C:\\Program Files (x86)\\{app_name}\\{app_name}.exe",
        f"C:\\Users\\{username}\\AppData\\Local\\Programs\\{app_name}\\{app_name}.exe",
        f"C:\\Users\\{username}\\AppData\\Local\\{app_name}\\{app_name}.exe",
        f"C:\\Users\\{username}\\AppData\\Roaming\\{app_name}\\{app_name}.exe",
    ]

    for path in common_paths:
        if os.path.exists(path):
            try:
                subprocess.Popen(
                    [path],
                    creationflags=_DETACHED_PROCESS,
                )
                return True
            except Exception:
                continue
    return False


def _try_where_command(app_name: str) -> bool:
    """尝试使用where命令查找并启动应用程序."""
    try:
        result = subprocess.run(
            ["where", app_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            exe_path = result.stdout.strip().split("\n")[0]
            if exe_path and os.path.exists(exe_path):
                subprocess.Popen(
                    [exe_path],
                    creationflags=_DETACHED_PROCESS,
                )
                return True
    except Exception as e:
        logger.debug(f"[WindowsLauncher] where.exe 查找应用失败: {e}")
    return False


def _try_uwp_launch(app_name: str) -> bool:
    """尝试启动UWP应用程序."""
    try:
        return _launch_uwp_app(app_name)
    except Exception:
        return False


def _find_executable_in_registry(app_name: str) -> str | None:
    """通过注册表查找应用程序的可执行文件路径.

    Args:
        app_name: 应用程序名称

    Returns:
        应用程序路径，如果没找到则返回None
    """
    try:
        import winreg

        registry_paths = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ]

        for registry_path in registry_paths:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as subkey:
                                try:
                                    display_name = winreg.QueryValueEx(
                                        subkey, "DisplayName"
                                    )[0]
                                    if app_name.lower() in display_name.lower():
                                        try:
                                            install_location = winreg.QueryValueEx(
                                                subkey, "InstallLocation"
                                            )[0]
                                            if install_location and os.path.exists(
                                                install_location
                                            ):
                                                for root, _dirs, files in os.walk(
                                                    install_location
                                                ):
                                                    for file in files:
                                                        if (
                                                            file.lower().endswith(
                                                                ".exe"
                                                            )
                                                            and app_name.lower()
                                                            in file.lower()
                                                        ):
                                                            return os.path.join(
                                                                root, file
                                                            )
                                        except FileNotFoundError:
                                            pass

                                        try:
                                            display_icon = winreg.QueryValueEx(
                                                subkey, "DisplayIcon"
                                            )[0]
                                            if (
                                                display_icon
                                                and display_icon.endswith(".exe")
                                                and os.path.exists(display_icon)
                                            ):
                                                return display_icon
                                        except FileNotFoundError:
                                            pass

                                except FileNotFoundError:
                                    continue
                        except Exception:
                            continue
            except Exception:
                continue

        return None

    except ImportError:
        logger.debug("[WindowsLauncher] winreg模块不可用，跳过注册表查找")
        return None
    except Exception as e:
        logger.debug(f"[WindowsLauncher] 注册表查找失败: {e}")
        return None


def _launch_uwp_app(app_name: str) -> bool:
    """尝试启动 UWP（Windows Store）应用程序.

    通过 $env:_APP_QUERY 环境变量传递应用名称，
    避免将用户输入直接拼接到 PowerShell 脚本中。

    Args:
        app_name: 应用程序名称

    Returns:
        启动是否成功
    """
    try:
        # 脚本从环境变量读取查询字符串，不含用户输入
        powershell_script = (
            "$q = $env:_APP_QUERY\n"
            "$app = Get-AppxPackage "
            '| Where-Object {$_.Name -like "*$q*" '
            '-or $_.PackageFullName -like "*$q*"} '
            "| Select-Object -First 1\n"
            "if ($app) {\n"
            "    $manifest = Get-AppxPackageManifest $app.PackageFullName\n"
            "    $appId = $manifest.Package.Applications.Application.Id\n"
            "    if ($appId) {\n"
            '        Start-Process "shell:AppsFolder\\$($app.PackageFullName)!$appId"\n'
            '        Write-Output "Success"\n'
            "    }\n"
            "}"
        )

        encoded = base64.b64encode(powershell_script.encode("utf-16-le")).decode(
            "ascii"
        )

        env = os.environ.copy()
        env["_APP_QUERY"] = app_name

        result = subprocess.run(
            ["powershell", "-EncodedCommand", encoded],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )

        if result.returncode == 0 and "Success" in result.stdout:
            return True

    except Exception as e:
        logger.debug(f"[WindowsLauncher] UWP启动异常: {e}")

    return False
