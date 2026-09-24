# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 The ITR2 Chinese Patch Authors
"""构建 v2 交付包（release_zh + zip）。

产物（相对本脚本所在仓库目录）：
  release_zh/           交付目录
  ITR2_Chinese_v2.zip   压缩包
"""
import hashlib
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = os.path.dirname(os.path.abspath(__file__))
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
    [switch]$Scan,
    [switch]$CleanOld,
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

function Show-Banner([string]$title) {
    Write-Host ''
    Write-Host ('=' * 62)
    Write-Host ('  Into the Radius 2 简体中文补丁 · ' + $title)
    Write-Host ('=' * 62)
}

# ---- 既有汉化/补丁残留扫描与清理 ----
# 分级处理：本补丁文件、非 en 语言目录、松散 locres、旧的 DefaultCulture 配置为
# 「确定项」，可直接清理；其它 *_P.pak、~mods、LogicMods 内容可能是别的 mod，
# 一律列出清单并逐个询问，直接回车 = 保留（绝不误删）。
function Get-Residue([string]$root) {
    $paks = Join-Path $root 'IntoTheRadius2\Content\Paks'
    $loc = Join-Path $root 'IntoTheRadius2\Content\Localization\Game'
    $own = @(); $patch = @(); $mods = @(); $logic = @(); $lang = @(); $loose = @(); $cfg = @()
    foreach ($f in $PatchFiles) {
        if (Test-Path -LiteralPath (Join-Path $paks $f)) { $own += $f }
    }
    if (Test-Path -LiteralPath $paks) {
        foreach ($f in @(Get-ChildItem -LiteralPath $paks -File -Filter '*.pak' -ErrorAction SilentlyContinue)) {
            if ($PatchFiles -notcontains $f.Name -and $f.Name -ne 'pakchunk0-Windows.pak') { $patch += $f.FullName }
        }
        foreach ($sub in @('~mods', 'LogicMods')) {
            $d = Join-Path $paks $sub
            if (Test-Path -LiteralPath $d) {
                $items = @(Get-ChildItem -LiteralPath $d -File -Recurse -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
                if ($sub -eq '~mods') { $mods = $items } else { $logic = $items }
            }
        }
    }
    foreach ($n in @('zh-Hans', 'zh-Hant', 'zh', 'chs', 'cht', 'zh_CN', 'zh_TW')) {
        $p = Join-Path $loc $n
        if (Test-Path -LiteralPath $p) { $lang += $p }
    }
    if (Test-Path -LiteralPath $loc) {
        foreach ($f in @(Get-ChildItem -LiteralPath $loc -Recurse -File -ErrorAction SilentlyContinue)) {
            if (($f.Extension -eq '.locres' -or $f.Extension -eq '.locmeta') -and $f.FullName -notmatch '\\en\\') {
                $inLang = $false
                foreach ($d in $lang) {
                    if ($f.FullName.StartsWith($d, [System.StringComparison]::OrdinalIgnoreCase)) { $inLang = $true }
                }
                if (-not $inLang) { $loose += $f.FullName }
            }
        }
    }
    foreach ($rel in @('IntoTheRadius2\Saved\Config\Windows\DeviceProfiles.ini',
                       'IntoTheRadius2\Saved\Config\Windows\Game.ini')) {
        $c = Join-Path $root $rel
        if (Test-Path -LiteralPath $c) {
            $hits = @(Get-Content -LiteralPath $c -ErrorAction SilentlyContinue |
                      Where-Object { $_ -match '^\s*DefaultCulture\s*=' })
            if ($hits.Count -gt 0) { $cfg += $c }
        }
    }
    return [pscustomobject]@{
        Own = $own; Patch = $patch; Mods = $mods; Logic = $logic
        Lang = $lang; Loose = $loose; Config = $cfg
    }
}

function Show-Residue($r) {
    if ($r.Own.Count)   { Write-Host ('  · 本补丁的旧安装文件: ' + $r.Own.Count + ' 个') }
    if ($r.Lang.Count)  { Write-Host ('  · 旧版松散汉化语言目录: ' + $r.Lang.Count + ' 个')
                          foreach ($p in $r.Lang) { Write-Host ('      ' + $p) } }
    if ($r.Loose.Count) { Write-Host ('  · 非 en 的松散本地化文件: ' + $r.Loose.Count + ' 个')
                          foreach ($p in $r.Loose) { Write-Host ('      ' + $p) } }
    if ($r.Patch.Count) { Write-Host ('  · 其它补丁 pak（可能是别的汉化/补丁）: ' + $r.Patch.Count + ' 个')
                          foreach ($p in $r.Patch) { Write-Host ('      ' + $p) } }
    if ($r.Mods.Count)  { Write-Host ('  · ~mods 目录内容: ' + $r.Mods.Count + ' 个')
                          foreach ($p in $r.Mods) { Write-Host ('      ' + $p) } }
    if ($r.Logic.Count) { Write-Host ('  · LogicMods 目录内容: ' + $r.Logic.Count + ' 个')
                          foreach ($p in $r.Logic) { Write-Host ('      ' + $p) } }
    if ($r.Config.Count){ Write-Host ('  · 配置中的 DefaultCulture 设置: ' + $r.Config.Count + ' 个')
                          foreach ($p in $r.Config) { Write-Host ('      ' + $p) } }
}

function Invoke-CleanResidue([string]$root, $r) {
    $paks = Join-Path $root 'IntoTheRadius2\Content\Paks'
    $n = 0
    foreach ($f in $r.Own) {
        $p = Join-Path $paks $f
        if (Test-Path -LiteralPath $p) {
            Remove-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue
            Write-Host "[OK] 已删除 $f"; $n++
        }
    }
    foreach ($d in $r.Lang) {
        if (Test-Path -LiteralPath $d) {
            Remove-Item -LiteralPath $d -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host ('[OK] 已删除语言目录 ' + $d); $n++
        }
    }
    foreach ($f in $r.Loose) {
        if (Test-Path -LiteralPath $f) {
            Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue
            Write-Host ('[OK] 已删除 ' + $f); $n++
        }
    }
    foreach ($c in $r.Config) {
        $before = @(Get-Content -LiteralPath $c)
        $after = @($before | Where-Object { $_ -notmatch '^\s*DefaultCulture\s*=' })
        if ($after.Count -ne $before.Count) {
            # 无 BOM UTF-8 写回：PowerShell 5.1 的 -Encoding UTF8 会写入 BOM，
            # 可能使配置首节失效
            [System.IO.File]::WriteAllLines($c, $after, (New-Object System.Text.UTF8Encoding($false)))
            Write-Host ('[OK] 已清理 ' + $c + ' 中的 DefaultCulture 设置'); $n++
        }
    }
    foreach ($f in @($r.Patch + $r.Mods + $r.Logic)) {
        Write-Host ''
        Write-Host ('[?] 疑似其它来源的文件: ' + $f) -ForegroundColor Yellow
        $ans = ''
        try { $ans = Read-Host '    删除请按 D 后回车，直接回车 = 保留' } catch { $ans = '' }
        if ($ans -eq 'D' -or $ans -eq 'd') {
            Remove-Item -LiteralPath $f -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host '[OK] 已删除'
            $n++
        } else {
            Write-Host '[skip] 已保留'
        }
    }
    return $n
}

Show-Banner $(if ($Scan) { '汉化残留扫描' }
              elseif ($CleanOld) { '汉化残留清理' }
              elseif ($Uninstall) { '卸载向导' }
              else { '安装向导' })
if (-not $Scan -and -not $CleanOld -and -not $Uninstall) {
    Write-Host '[教程] 安装流程（约 1 分钟，无需启动参数）：'
    Write-Host '  1. 前置检查：确认游戏版本、退出游戏、具备写入权限'
    Write-Host '  2. 安装补丁：将补丁文件复制到游戏 Paks 目录'
    Write-Host '  3. 启动验证：进入游戏确认界面为简体中文'
    Write-Host '  详细说明与常见问题见随包《汉化说明.md》。'
    Write-Host ''
    Write-Host '-- 步骤 1/3 前置检查 --'
}
if (-not $GameDir) { $GameDir = Find-GameDir }
if (-not $GameDir -or
    -not (Test-Path -LiteralPath $GameDir -ErrorAction SilentlyContinue) -or
    -not (Test-Path -LiteralPath (Join-Path $GameDir 'IntoTheRadius2.exe') -ErrorAction SilentlyContinue)) {
    Write-Host '[X] 找不到 Into the Radius 2 安装目录，请手动指定：' -ForegroundColor Red
    Write-Host "    powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 -GameDir 'D:\SteamLibrary\steamapps\common\IntoTheRadius2'"
    Write-Host '    若仍无法解决，请参阅随包《汉化说明.md》第一节。'
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

$residue = Get-Residue $GameDir
$residueTotal = $residue.Own.Count + $residue.Patch.Count + $residue.Mods.Count +
                $residue.Logic.Count + $residue.Lang.Count + $residue.Loose.Count + $residue.Config.Count

if ($Scan) {
    Write-Host ''
    Write-Host '-- 扫描既有汉化 / 补丁残留 --'
    if ($residueTotal -eq 0) {
        Write-Host '[OK] 未发现既有汉化或补丁残留。'
    } else {
        Write-Host "[i] 共发现 $residueTotal 项："
        Show-Residue $residue
        Write-Host ''
        Write-Host '[教程] 清理方式：运行安装器并选择 [4]，或执行 install.ps1 -CleanOld。'
    }
    exit 0
}

if ($CleanOld) {
    Write-Host ''
    Write-Host '-- 清理既有汉化 / 补丁残留 --'
    if ($residueTotal -eq 0) {
        Write-Host '[OK] 未发现既有汉化或补丁残留，无需清理。'
        exit 0
    }
    Write-Host "[i] 共发现 $residueTotal 项："
    Show-Residue $residue
    Write-Host ''
    $cleaned = Invoke-CleanResidue $GameDir $residue
    Write-Host ''
    Write-Host "[OK] 清理完成，共处理 $cleaned 项。"
    Write-Host '[教程] 重新汉化：运行安装器并选择 [1] 安装简体中文补丁。'
    Write-Host '  · 若 Steam 启动选项里留有 -CULTURE=... 参数，请一并删除。'
    exit 0
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
                [System.IO.File]::WriteAllLines($cf, $after, (New-Object System.Text.UTF8Encoding($false)))
                Write-Host "[OK] 已清理 $rel 中的旧版 DefaultCulture 设置"
            }
        }
    }
    Write-Host ''
    Write-Host '[OK] 卸载完成（共移除 $n 个补丁文件），游戏已还原为英文原版。'
    Write-Host '[教程] 后续：'
    Write-Host '  · 重新安装：再次运行「安装汉化.cmd」。'
    Write-Host '  · 若启动项中留有 -CULTURE=zh-Hans 参数，请一并删除。'
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

if ($residueTotal -gt 0) {
    Write-Host "[!] 发现 $residueTotal 项既有汉化 / 补丁残留（可能与本补丁冲突）：" -ForegroundColor Yellow
    Show-Residue $residue
    $certain = $residue.Own.Count + $residue.Lang.Count + $residue.Loose.Count + $residue.Config.Count
    if ($certain -gt 0) {
        Write-Host ''
        $ans = ''
        try { $ans = Read-Host '[?] 先清理本补丁旧安装文件与旧版松散汉化残留？(Y/N，回车 = 否)' } catch { $ans = '' }
        if ($ans -eq 'Y' -or $ans -eq 'y') {
            $only = [pscustomobject]@{
                Own = $residue.Own; Lang = $residue.Lang; Loose = $residue.Loose
                Config = $residue.Config; Patch = @(); Mods = @(); Logic = @()
            }
            $cleaned = Invoke-CleanResidue $GameDir $only
            Write-Host "[OK] 已清理 $cleaned 项旧安装残留。"
        } else {
            Write-Host '[skip] 保留现有文件，继续安装（同名文件将被覆盖）。'
        }
    }
    if ($residue.Patch.Count -gt 0 -or $residue.Mods.Count -gt 0 -or $residue.Logic.Count -gt 0) {
        Write-Host '[i] 其它来源的文件未自动处理；如需彻底清理，请运行安装器选择 [4] 逐个确认。'
    }
}
Write-Host '[OK] 前置检查通过'

Write-Host ''
Write-Host '-- 步骤 2/3 安装补丁 --'
$copied = 0
foreach ($f in $PatchFiles) {
    if ($f -eq $FontFile -and $NoFont) { Write-Host "[skip] $f（已指定 -NoFont）"; continue }
    $src = Join-Path $packRoot $f
    if (-not (Test-Path $src)) { Write-Host "[!] 缺少文件: $f" -ForegroundColor Yellow; continue }
    Copy-Item $src (Join-Path $paks $f) -Force
    Write-Host "[OK] 已安装 $f"
    $copied++
}
Write-Host ''
Write-Host '-- 步骤 3/3 安装完成 --'
Write-Host "[OK] 共安装 $copied 个补丁文件。"
Write-Host '[教程] 后续使用：'
Write-Host '  · 直接启动游戏，界面、任务、物品说明与字幕为简体中文（无需启动参数或语言设置）。'
Write-Host '  · 文字显示为方框或空白：请改用「不含字体」方式安装，并到发布页反馈。'
Write-Host '  · 游戏更新后中文失效：请先卸载，待补丁更新后重新安装。'
Write-Host '  · 卸载或重新安装：重新运行安装程序并选择对应选项（压缩包版可双击对应 .cmd）。'
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

CMD_CLEAN = '''@echo off
chcp 936 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -CleanOld
echo.
pause
'''

CMD_SCAN = '''@echo off
chcp 936 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Scan
echo.
pause
'''

README = '''# Into the Radius 2 简体中文汉化包 v2

适用版本：**{version}**（Steam buildid `{build}`，appid 2307350）
安装方式：**patch pak（覆盖 `en` 语言资源）**——不需要启动参数，不需要在游戏里切换语言。

---

## 一、安装

### 方式一：单文件安装器（推荐）

下载 **`ITR2简体中文补丁v2_安装器.exe`**，放入游戏目录或任意位置，**双击运行**，
按提示选择 `[1] 安装简体中文补丁`。安装器会自动定位 Steam 游戏目录并完成复制；
若文字显示为方框，可重新运行并选择 `[2] 安装（不含字体覆盖）`。

### 方式二：压缩包

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

### 安装前的残留清理（可选）

若游戏内此前装过其它汉化或旧版补丁，可先运行安装器选择 `[4] 扫描并清理既有汉化残留`
（压缩包版双击 `清理旧汉化.cmd`；只查看不清理可双击 `扫描汉化残留.cmd`）。

清理规则：本补丁旧文件、旧版松散语言目录（`zh-Hans` 等）、非 `en` 的本地化文件、
配置里的旧 `DefaultCulture` 行会直接清理；其它 `*_P.pak`、`~mods`、`LogicMods` 内容
**逐项询问**，直接回车即保留——不会误删你安装的其它 mod。

## 二、卸载

单文件安装器：重新运行并选择 `[3] 卸载补丁`；压缩包版：双击 `卸载汉化.cmd`。
两者都会删除上述 5 个文件，并顺手清理旧版(v1)留下的
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

- 构建工具为**独立实现**；文件格式事实与哈希公式（`source_hash = CRC32(UTF-32LE)`、
  `key_hash = CityHash64(UTF-16LE)` 折叠）参考了开源项目 [refracta/itr2-ko](https://github.com/refracta/itr2-ko)
  的公开说明，以及“locres + uasset 必须同时打”的结论。全部格式实现均以游戏原文件
  与发布产物逐字节自校验；未复制、未加载该项目的任何代码与数据文件。
- 中文术语参考中文社区现有汉化（Nexus 258/304）与游戏内语境（半径、神器、拟态怪、佩乔尔斯克异常、UNPSC 等）。
- 字体取自游戏自身资源（`NotoSansSC-Regular/Bold`），其上游为 **SIL Open Font License 1.1** 授权的
  Noto Sans SC；本包已随附许可证全文（`licenses\\OFL-NotoSansSC.txt`），依该许可不得单独售卖字体本身。
- 想在不戴头显的情况下快速验证文字：可参考韩化项目的 `tools/vr-kbm-test-driver`（SteamVR 假 HMD 驱动）。

## 七、授权与声明

- 本补丁的脚本与简体中文译文以 **Apache License 2.0** 授权，许可证全文见随包 `LICENSE`，
  第三方内容清单、修改说明与致谢见随包 `NOTICE`。
- 本补丁为**非官方爱好者汉化**。《Into the Radius 2》的游戏资源版权归 **CM Games** 所有，
  本项目与其无从属关系，亦未获其背书，请勿用于商业用途。
- 构建工具为独立实现，文件格式事实参考了开源项目 [refracta/itr2-ko](https://github.com/refracta/itr2-ko)；
  该项目未声明许可证，其源代码与数据文件未复制、未随本包分发。
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

# ---- 单文件安装器（IExpress 自解压 exe，Windows 自带工具，零第三方依赖）----
# IExpress 不支持子目录且对非 ASCII 路径不可靠：暂存目录用 ASCII 名、载荷平铺、
# 文件名全部 ASCII（生成后再由本脚本改名为中文友好名）。
SFX_STAGE = os.path.join(ROOT, "_sfx_stage")
SFX_EXE_TMP = os.path.join(ROOT, "ITR2_ZH_Patch_v2_Setup.exe")
SFX_EXE = os.path.join(ROOT, "ITR2简体中文补丁v2_安装器.exe")
SFX_EXTRA = ["LICENSE", "NOTICE", "OFL-NotoSansSC.txt", "README-zh.md"]

INSTALL_CMD_SFX = '''@echo off
chcp 936 >nul
cd /d "%~dp0"
title Into the Radius 2 简体中文补丁 · 安装器
echo [%DATE% %TIME%] 单文件安装器启动 >> "%TEMP%\\ITR2_installer_launch.log"

echo.
echo   Into the Radius 2 简体中文补丁 · 单文件安装器 v2
echo   ------------------------------------------------------------
echo    [1] 安装简体中文补丁（推荐）
echo    [2] 安装（不含字体覆盖）
echo    [3] 卸载补丁
echo    [4] 扫描并清理既有汉化残留
echo    [0] 退出
echo.
echo   说明：安装器自动定位 Steam 游戏目录；把本文件放进游戏目录再运行亦可。
echo.
set "CH="
set /p "CH=请输入选项并回车（直接回车 = 1）: "
if not defined CH set "CH=1"

if "%CH%"=="1" powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if "%CH%"=="2" powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -NoFont
if "%CH%"=="3" powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Uninstall
if "%CH%"=="4" powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -CleanOld
if "%CH%"=="0" exit /b 0

echo.
pause
'''


def build_installer():
    """生成单文件安装器（IExpress 自解压 exe）。

    载荷平铺且全部 ASCII 文件名：install.cmd（菜单入口）+ install.ps1 + 5 个补丁 pak
    + 许可证/声明/说明。运行后解压目录会被系统清理，安装动作在此之前完成。
    """
    iexpress = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "iexpress.exe")
    if not os.path.exists(iexpress):
        print("[!] 跳过单文件安装器：未找到 iexpress.exe（该功能仅 Windows 提供）")
        return None

    if os.path.isdir(SFX_STAGE):
        shutil.rmtree(SFX_STAGE)
    os.makedirs(SFX_STAGE)
    with open(os.path.join(SFX_STAGE, "install.cmd"), "w", encoding="gbk", newline="\r\n") as f:
        f.write(INSTALL_CMD_SFX)
    shutil.copy2(os.path.join(REL, "install.ps1"), SFX_STAGE)
    for f in FILES:
        shutil.copy2(os.path.join(REL, f), SFX_STAGE)
    shutil.copy2(os.path.join(REL, "LICENSE"), SFX_STAGE)
    shutil.copy2(os.path.join(REL, "NOTICE"), SFX_STAGE)
    shutil.copy2(os.path.join(REL, "licenses", "OFL-NotoSansSC.txt"), SFX_STAGE)
    shutil.copy2(os.path.join(REL, "汉化说明.md"), os.path.join(SFX_STAGE, "README-zh.md"))

    load = ["install.cmd", "install.ps1"] + list(FILES) + SFX_EXTRA
    lines = [
        "[Version]", "Class=IEXPRESS", "SEDVersion=3",
        "[Options]", "PackagePurpose=InstallApp",
        "ShowInstallProgramWindow=0", "HideExtractAnimation=1", "UseLongFileName=1",
        "InsideCompressed=0", "CAB_FixedSize=0", "CAB_ResvCodeSigning=0", "RebootMode=N",
        "InstallPrompt=", "DisplayLicense=", "FinishMessage=",
        "TargetName=" + SFX_EXE_TMP,
        "FriendlyName=Into the Radius 2 Chinese Patch v2",
        "AppLaunched=install.cmd",
        "PostInstallCmd=<None>", "AdminQuietInstCmd=", "UserQuietInstCmd=",
        "SourceFiles=SourceFiles", "[Strings]",
    ]
    lines += ['FILE%d="%s"' % (i, n) for i, n in enumerate(load)]
    lines += ["[SourceFiles]", "SourceFiles0=" + SFX_STAGE + "\\", "[SourceFiles0]"]
    lines += ["%%FILE%d%%=" % i for i in range(len(load))]
    sed_path = os.path.join(SFX_STAGE, "itr2_zh.sed")
    with open(sed_path, "w", encoding="ascii", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")

    if os.path.exists(SFX_EXE_TMP):
        os.remove(SFX_EXE_TMP)
    print("[i] 正在生成单文件安装器（IExpress 压缩 %d 个文件，约需 1-3 分钟）…" % len(load))
    r = subprocess.run([iexpress, "/N", "/Q", sed_path], capture_output=True, timeout=900)
    if r.returncode != 0 or not os.path.exists(SFX_EXE_TMP):
        print("[!] 单文件安装器生成失败（iexpress 退出码 %s）：%s"
              % (r.returncode, r.stdout.decode("gbk", "replace")[-400:]))
        return None
    if os.path.exists(SFX_EXE):
        os.remove(SFX_EXE)
    shutil.move(SFX_EXE_TMP, SFX_EXE)
    shutil.rmtree(SFX_STAGE, ignore_errors=True)
    print("[setup] %s  %d B" % (os.path.basename(SFX_EXE), os.path.getsize(SFX_EXE)))
    return SFX_EXE


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    # 1) 组装交付目录
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
        ("清理旧汉化.cmd", CMD_CLEAN, "gbk"),
        ("扫描汉化残留.cmd", CMD_SCAN, "gbk"),
    ):
        with open(os.path.join(REL, name), "w", encoding=enc, newline="\r\n") as f:
            f.write(body)
    with open(os.path.join(REL, "汉化说明.md"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(README.format(version=GAME_VERSION, build=GAME_BUILD, hashes=hashes))
    with open(os.path.join(REL, "版本信息.json"), "w", encoding="utf-8") as f:
        json.dump(INFO, f, ensure_ascii=False, indent=2)

    # 2) 打包 zip（含 licenses/ 子目录）
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

    # 3) 单文件安装器
    build_installer()


if __name__ == "__main__":
    main()
