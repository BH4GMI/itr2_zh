# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The ITR2 Chinese Patch Authors
"""构建 v2 交付包（release_zh + zip），并清理已作废的 v1 松散文件包。

产物：
  D:\\SteamLibrary\\steamapps\\common\\itr2_zh\\release_zh\\           交付目录
  D:\\SteamLibrary\\steamapps\\common\\itr2_zh\\ITR2_Chinese_v2.zip   压缩包
"""
import hashlib
import json
import os
import shutil
import zipfile

ROOT = r"D:\SteamLibrary\steamapps\common\itr2_zh"
DIST = os.path.join(ROOT, "dist_zh")
REL = os.path.join(ROOT, "release_zh")
ZIP = os.path.join(ROOT, "ITR2_Chinese_v2.zip")

FILES = [
    "pakchunk99-ZH_Locres_P.pak",
    "pakchunk99-ZH_UAsset-Windows.pak",
    "pakchunk99-ZH_UAsset-Windows.utoc",
    "pakchunk99-ZH_UAsset-Windows.ucas",
    "pakchunk100-ZH_Fonts_P.pak",
]

GAME_BUILD = "24024260"
GAME_VERSION = "Hotfix Patch 1.1.2"

INSTALL_PS1 = r'''param(
    [switch]$Uninstall,
    [switch]$NoFont,
    [string]$GameDir = ''
)
$ErrorActionPreference = 'Stop'
$packRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

$PatchFiles = @(
    'pakchunk99-ZH_Locres_P.pak',
    'pakchunk99-ZH_UAsset-Windows.pak',
    'pakchunk99-ZH_UAsset-Windows.utoc',
    'pakchunk99-ZH_UAsset-Windows.ucas',
    'pakchunk100-ZH_Fonts_P.pak'
)
$FontFile = 'pakchunk100-ZH_Fonts_P.pak'
$ExpectedBuild = '24024260'
$ExpectedVersion = 'Hotfix Patch 1.1.2'

function Find-GameDir {
    $cands = New-Object System.Collections.Generic.List[string]
    foreach ($d in (Get-PSDrive -PSProvider FileSystem).Root) {
        $cands.Add((Join-Path $d 'SteamLibrary\steamapps\common\IntoTheRadius2'))
        $cands.Add((Join-Path $d 'Steam\steamapps\common\IntoTheRadius2'))
        $cands.Add((Join-Path $d 'Program Files (x86)\Steam\steamapps\common\IntoTheRadius2'))
        $cands.Add((Join-Path $d 'Games\IntoTheRadius2'))
    }
    $cands.Add('C:\Program Files (x86)\Steam\steamapps\common\IntoTheRadius2')
    foreach ($c in $cands) {
        if (Test-Path (Join-Path $c 'IntoTheRadius2.exe')) { return $c }
    }
    return ''
}

function Show-VersionCheck([string]$root) {
    try {
        $steamapps = Split-Path -Parent (Split-Path -Parent $root)
        $acf = Join-Path $steamapps 'appmanifest_2307350.acf'
        if (Test-Path $acf) {
            $line = (Get-Content $acf | Where-Object { $_ -match '"buildid"' } | Select-Object -First 1)
            if ($line) {
                $build = ($line -replace '[^0-9]', '')
                Write-Host ("[i] 游戏 buildid = " + $build + "（本补丁基准 " + $ExpectedBuild + " / " + $ExpectedVersion + "）")
                if ($build -ne $ExpectedBuild) {
                    Write-Host '[!] buildid 与补丁基准不一致：游戏更新后 locres/uasset 偏移可能变化，补丁可能部分或全部失效。' -ForegroundColor Yellow
                }
            }
        }
    } catch { }
}

if (-not $GameDir) { $GameDir = Find-GameDir }
if (-not $GameDir -or -not (Test-Path (Join-Path $GameDir 'IntoTheRadius2.exe'))) {
    Write-Host '[X] 找不到 Into the Radius 2 安装目录，请手动指定：' -ForegroundColor Red
    Write-Host "    powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 -GameDir 'D:\SteamLibrary\steamapps\common\IntoTheRadius2'"
    exit 1
}

$paks = Join-Path $GameDir 'IntoTheRadius2\Content\Paks'
Write-Host "[i] 游戏目录: $GameDir"
Write-Host "[i] Paks 目录: $paks"
Show-VersionCheck $GameDir

# 游戏运行中会占用 pak 文件，必须先行退出，否则覆盖会失败
$running = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like 'IntoTheRadius2*' })
if ($running.Count -gt 0) {
    Write-Host '[X] 检测到游戏正在运行（IntoTheRadius2.exe），请先完全退出游戏后再执行本脚本。' -ForegroundColor Red
    foreach ($p in $running) { Write-Host ("    运行中的进程: " + $p.ProcessName + " (PID " + $p.Id + ")") }
    exit 1
}

if ($Uninstall) {
    $n = 0
    foreach ($f in $PatchFiles) {
        $p = Join-Path $paks $f
        if (Test-Path $p) { Remove-Item $p -Force; Write-Host "[OK] 已删除 $f"; $n++ }
    }
    $oldLoc = Join-Path $GameDir 'IntoTheRadius2\Content\Localization\Game\zh-Hans'
    if (Test-Path $oldLoc) {
        Remove-Item $oldLoc -Recurse -Force
        Write-Host '[OK] 已清理旧版(v1)残留: Content\Localization\Game\zh-Hans'
    }
    foreach ($rel in @('IntoTheRadius2\Saved\Config\Windows\DeviceProfiles.ini', 'IntoTheRadius2\Saved\Config\Windows\Game.ini')) {
        $cf = Join-Path $GameDir $rel
        if (Test-Path $cf) {
            $before = @(Get-Content $cf)
            $after = @($before | Where-Object { $_ -notmatch '^\s*DefaultCulture\s*=' })
            if ($after.Count -ne $before.Count) {
                Set-Content -Path $cf -Value $after -Encoding UTF8
                Write-Host "[OK] 已清理 $rel 中的旧版 DefaultCulture 设置"
            }
        }
    }
    Write-Host "[OK] 卸载完成（共移除 $n 个补丁文件）。若启动项里还留着 -CULTURE=zh-Hans，请一并删掉。"
    exit 0
}

if (-not (Test-Path $paks)) {
    Write-Host "[X] 目录不存在: $paks" -ForegroundColor Red
    Write-Host '    请确认 -GameDir 指向的是游戏根目录（含 IntoTheRadius2.exe）。'
    exit 1
}

# 写入权限检查：Steam 库若位于 Program Files 等受保护位置，需要以管理员身份运行
$probe = Join-Path $paks ('.itr2zh_write_test_' + [guid]::NewGuid().ToString('N'))
$writable = $true
try {
    Set-Content -Path $probe -Value 'test' -ErrorAction Stop
    Remove-Item $probe -Force -ErrorAction SilentlyContinue
} catch {
    $writable = $false
}
if (-not $writable) {
    Write-Host '[X] 没有写入权限，无法安装到该目录。' -ForegroundColor Red
    Write-Host '    请右键点击 安装汉化.cmd，选择“以管理员身份运行”。'
    exit 1
}

$others = @(Get-ChildItem $paks -Filter '*_P.pak' -ErrorAction SilentlyContinue | Where-Object { $PatchFiles -notcontains $_.Name })
if ($others.Count -gt 0) {
    Write-Host '[!] 检测到其它补丁 pak，可能与本补丁冲突；如遇异常请先移除：' -ForegroundColor Yellow
    foreach ($o in $others) { Write-Host ("    " + $o.Name) }
}

$copied = 0
foreach ($f in $PatchFiles) {
    if ($f -eq $FontFile -and $NoFont) { Write-Host "[skip] $f（已指定 -NoFont）"; continue }
    $src = Join-Path $packRoot $f
    if (-not (Test-Path $src)) { Write-Host "[!] 缺少文件: $f" -ForegroundColor Yellow; continue }
    Copy-Item $src (Join-Path $paks $f) -Force
    Write-Host "[OK] 已安装 $f"
    $copied++
}
Write-Host "[OK] 安装完成（共 $copied 个文件）。直接启动游戏即可，无需启动参数，亦无需在设置中切换语言。"
Write-Host '[i] 授权信息见随包 LICENSE、NOTICE 与 licenses\OFL-NotoSansSC.txt。'
'''

CMD_INSTALL = '''@echo off
chcp 936 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
echo.
pause
'''

CMD_INSTALL_NOFONT = '''@echo off
chcp 936 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -NoFont
echo.
pause
'''

CMD_UNINSTALL = '''@echo off
chcp 936 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Uninstall
echo.
pause
'''

README = '''# Into the Radius 2 简体中文汉化包 v2

适用版本：**{version}**（Steam buildid `{build}`，appid 2307350）
安装方式：**patch pak（覆盖 `en` 语言资源）**——不需要启动参数，不需要在游戏里切换语言。

---

## 一、安装

1. 把压缩包解压到任意位置（不要放在游戏目录里也行）。
2. **双击 `安装汉化.cmd`**。脚本会自动找到 Steam 游戏目录，把 5 个补丁文件复制进
   `...\\IntoTheRadius2\\Content\\Paks\\`。
3. 启动游戏。UI、任务、物品说明、字幕应当显示为简体中文。

手动安装（脚本失败时）：把下面 5 个文件复制到 `...\\steamapps\\common\\IntoTheRadius2\\IntoTheRadius2\\Content\\Paks\\`

```
pakchunk99-ZH_Locres_P.pak
pakchunk99-ZH_UAsset-Windows.pak
pakchunk99-ZH_UAsset-Windows.utoc
pakchunk99-ZH_UAsset-Windows.ucas
pakchunk100-ZH_Fonts_P.pak      （字体覆盖，见第五节）
```

不想替换字体（例如你更想用系统字体方案）：双击 `安装汉化_不含字体.cmd`，或运行
`powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 -NoFont`。

## 二、卸载

双击 `卸载汉化.cmd`。它会删除上述 5 个文件，并顺手清理旧版(v1)留下的
`Content\\Localization\\Game\\zh-Hans\\` 目录和配置文件里的 `DefaultCulture` 行。

## 三、这一版包含什么

| 内容 | 说明 |
| --- | --- |
| `Game.locres`（4611 条） | 覆盖 `Content/Localization/Game/en/Game.locres`：原 2164 条 + `EnglishSource` 命名空间合并 2447 条 |
| `EnglishSource.uasset` | IoStore override（挂载点 `../../../Projectc/Content/ITR2/Configurations/Localization/`），3332 条里 3019 条替换为中文 |
| 字体覆盖 | 用**游戏自带的 Noto Sans SC**（20,976 个汉字、189 个假名）替换 3 个离线字体 `.ufont` |

**覆盖度：3772 / 3772 条唯一英文原文 = 100%**（旧版 v1 只覆盖 1282 条 = 34%，且用的是
松散文件 + `-CULTURE=` 启动参数，实测路线不成立，已作废）。

## 四、为什么必须打 pak

UE 在挂载时会先读 pak、再读松散文件，所以把 `Game.locres` 以松散文件方式放进
`Content\\Localization\\Game\\zh-Hans\\` **不会生效**；`-CULTURE=zh-Hans` 也不是本作的正确切换方式
（引擎只 stage 了 `en` 的 ICU 数据）。因此本包采用社区验证过的做法：
带 `_P` 后缀的 patch pak 在基础 pak 之后挂载，直接覆盖 `en` 资源。

## 五、已知限制

- **贴图上的文字**（路牌、海报等烘焙进纹理的英文）不会变，需要单独的贴图补丁。
- **`Engine.locres`（引擎层文案）**未汉化，出现频率低；社区各语言 mod 也都没做。
- **语音**仍为英文，本包不含配音（如需中文语音需另做音频替换）。
- **游戏更新后可能失效**：本补丁基准是 `{version}` / buildid `{build}`。
  游戏更新（尤其内容更新）后 locres 条目与 uasset 偏移会变，需要重新构建。
- 若文字显示为方框/空白：说明字体覆盖没生效。请反馈截图，并说明是否使用了 `-NoFont`。

## 六、技术与致谢

- 构建流程参考开源项目 [refracta/itr2-ko](https://github.com/refracta/itr2-ko)：
  其 IoStore 容器模板、`source_hash = CRC32(UTF-32LE)`、`key_hash = CityHash64(UTF-16LE)` 折叠算法，
  以及“locres + uasset 必须同时打”的结论，本包直接复用并已逐条自校验。
- 中文术语参考中文社区现有汉化（Nexus 258/304）与游戏内语境（半径、神器、拟态怪、佩乔尔斯克异常、UNPSC 等）。
- 字体取自游戏自身资源（`NotoSansSC-Regular/Bold`），其上游为 **SIL Open Font License 1.1** 授权的
  Noto Sans SC；本包已随附许可证全文（`licenses\\OFL-NotoSansSC.txt`），依该许可不得单独售卖字体本身。
- 想在不戴头显的情况下快速验证文字：可参考韩化项目的 `tools/vr-kbm-test-driver`（SteamVR 假 HMD 驱动）。

## 七、授权与声明

- 本补丁的脚本与简体中文译文以 **Apache License 2.0** 授权，许可证全文见随包 `LICENSE`，
  第三方内容清单、修改说明与致谢见随包 `NOTICE`。
- 本补丁为**非官方爱好者汉化**。《Into the Radius 2》的游戏资源版权归 **CM Games** 所有，
  本项目与其无从属关系，亦未获其背书，请勿用于商业用途。
- 构建过程参考了开源项目 [refracta/itr2-ko](https://github.com/refracta/itr2-ko)；
  该项目未声明许可证，其源代码与数据文件未随本包分发。
- Oodle 数据压缩运行库为 Epic Games / RAD Game Tools 专有，本包不含其代码
  （自建容器采用未压缩存储，解压由游戏程序自身完成）。

随包声明文件：

```
LICENSE                     Apache License 2.0 全文（本补丁脚本与译文）
NOTICE                      第三方内容清单、对上游内容的修改说明与致谢
licenses\\OFL-NotoSansSC.txt  Noto Sans SC 字体的 SIL OFL 1.1 许可证全文
```

## 八、文件校验（SHA1）

```
{hashes}
```
'''

INFO = {
    "name": "Into the Radius 2 简体中文汉化包",
    "version": "v2",
    "game": "Into the Radius 2 (Steam appid 2307350)",
    "base_game_version": GAME_VERSION,
    "base_game_buildid": GAME_BUILD,
    "type": "patch pak (IoStore/UFS override of 'en' localization)",
    "license": "Apache-2.0（本补丁脚本与译文）；字体为 SIL OFL 1.1；游戏资源版权归 CM Games",
    "coverage": {"unique_sources": 3772, "translated": 3772, "locres_entries": 4611,
                 "uasset_records": 3332, "uasset_changed": 3019},
    "files": FILES,
    "documents": ["LICENSE", "NOTICE", "licenses/OFL-NotoSansSC.txt", "汉化说明.md", "版本信息.json"],
}

# 随包分发的许可证与声明文件： (仓库内相对路径, 包内相对路径)
DOC_FILES = [
    ("LICENSE", "LICENSE"),
    ("NOTICE", "NOTICE"),
    (os.path.join("licenses", "OFL-NotoSansSC.txt"), os.path.join("licenses", "OFL-NotoSansSC.txt")),
]


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    # 1) 清理作废的 v1 松散文件包（翻译数据已合并进 records_with_zh.json / zh_sources.json）
    old = os.path.join(ROOT, "pack")
    if os.path.isdir(old):
        arch = os.path.join(ROOT, "archive")
        os.makedirs(arch, exist_ok=True)
        csv_src = os.path.join(old, "translations_zh-Hans.csv")
        if os.path.exists(csv_src):
            shutil.copy2(csv_src, os.path.join(arch, "v1_translations_zh-Hans.csv"))
        shutil.rmtree(old)
        print("[del] 已删除作废的 v1 包: pack\\  (CSV 备份到 archive\\v1_translations_zh-Hans.csv)")
    for junk in ("ref_ko/translations/unique_sources_with_ko.json",):
        p = os.path.join(ROOT, junk.replace("/", os.sep))
        if os.path.exists(p) and os.path.getsize(p) == 0:
            os.remove(p)
            print("[del] 已删除 0 字节残留:", junk)

    # 2) 组装交付目录
    if os.path.isdir(REL):
        shutil.rmtree(REL)
    os.makedirs(REL)
    for f in FILES:
        src = os.path.join(DIST, f)
        if not os.path.exists(src):
            raise SystemExit("缺少构建产物: " + src)
        shutil.copy2(src, os.path.join(REL, f))
    for src_rel, dst_rel in DOC_FILES:
        src = os.path.join(ROOT, src_rel)
        if not os.path.exists(src):
            raise SystemExit("缺少许可证/声明文件: " + src)
        dst = os.path.join(REL, dst_rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)

    hashes = "\n".join("%s  %s" % (sha1(os.path.join(REL, f)), f) for f in FILES)
    with open(os.path.join(REL, "install.ps1"), "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write(INSTALL_PS1)
    for name, body, enc in (
        ("安装汉化.cmd", CMD_INSTALL, "gbk"),
        ("安装汉化_不含字体.cmd", CMD_INSTALL_NOFONT, "gbk"),
        ("卸载汉化.cmd", CMD_UNINSTALL, "gbk"),
    ):
        with open(os.path.join(REL, name), "w", encoding=enc, newline="\r\n") as f:
            f.write(body)
    with open(os.path.join(REL, "汉化说明.md"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(README.format(version=GAME_VERSION, build=GAME_BUILD, hashes=hashes))
    with open(os.path.join(REL, "版本信息.json"), "w", encoding="utf-8") as f:
        json.dump(INFO, f, ensure_ascii=False, indent=2)

    # 3) 打包 zip（含 licenses/ 子目录）
    if os.path.exists(ZIP):
        os.remove(ZIP)
    with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for root, _dirs, names in os.walk(REL):
            for n in sorted(names):
                full = os.path.join(root, n)
                rel = os.path.relpath(full, REL).replace(os.sep, "/")
                zf.write(full, "ITR2_Chinese_v2/" + rel)

    print("\n[release] " + REL)
    for root, _dirs, names in os.walk(REL):
        for n in sorted(names):
            p = os.path.join(root, n)
            rel = os.path.relpath(p, REL)
            print("   %-38s %10d B" % (rel, os.path.getsize(p)))
    print("[zip] %s  %d B" % (ZIP, os.path.getsize(ZIP)))


if __name__ == "__main__":
    main()
