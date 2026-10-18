# 神威（Kamui）简体中文汉化

SITER SKAIN 2001 年同人纵版射击游戏《神威（KAMUI）》Steam 版（AppID 283820，内附 ver1.12 升级档）的简体中文汉化包与汉化工程。

## 汉化范围

| 内容 | 状态 |
| --- | --- |
| 启动器 SetupKamui.exe / config.exe | 已汉化（内嵌 GBK 资源字符串改写：开始游戏 / 退出 / 打开说明书 / 启动选项等） |
| 游戏说明书 manual.htm + manual/（13 页） | 已汉化（Shift-JIS 原文全文翻译，重存为 UTF-8） |
| 游戏内文字（标题 / 选项 / 关卡选择 / HUD） | 未汉化——游戏内文字为 DAR:8 打包的抖动点阵位图，按需求保持原样 |

## 安装方法

将 `patch/` 目录下的全部文件按原目录结构复制到游戏根目录（`...\Steam\steamapps\common\Kamui`）覆盖同名文件即可：

```
patch\SetupKamui.exe   -> 游戏根目录
patch\config.exe       -> 游戏根目录
patch\manual.htm       -> 游戏根目录
patch\manual\*.htm    -> 游戏根目录\manual
```

需要还原时，把 `originals/` 下的文件按同样方式复制回去覆盖即可。

## 目录结构

- `patch/` —— 汉化包（覆盖即用）
- `originals/` —— 汉化前原版文件（还原用）
- `tools/` —— 汉化工程脚本（DAR 解包、资源改写、截图 / OCR 等）
- `docs/` —— 工程笔记（DAR:8 格式分析、经验与坑）、DAR 条目清单、启动器汉化前后截图对比

## 版权

原游戏 © SITER SKAIN。本仓库仅供个人学习交流，请勿用于商业用途；游戏本体请通过 Steam 购买。
