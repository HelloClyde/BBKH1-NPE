# 来源

本仓库原创 H1 适配层（`src/`）、构建/打包脚本（`tools/`）与测试（`tests/`）
采用 GNU GPL version 2，完整文本见根目录 `LICENSE`。
从 BBKH1-GBA 改编的代码保留 GPL-2.0 来源；此许可不覆盖下列各自授权的第三方内容。

- NPE 引擎：HelloClyde/noah-npe-engine，提交 `7e156527d2d668b666fc203df2aadb929ab83de1`。
  原创引擎、前端、工具和测试源码按 GPL-2.0-only 授权，文本与范围见上游 `LICENSE`、`NOTICE.md`。
  H1 构建保持该固定子模块干净；上游本次仅增加许可文件和 README 说明。
- H1 运行时、freestanding libc、PCM、按键矩阵、触摸及诊断代码参考/改编自
  HelloClyde/BBKH1-GBA（GPL-2.0），硬件接口在提交
  `e73848f295508d92f45488b354735a35c9722477` 核对。对应许可证见 `assets/licenses/GPL-2.0.txt`。
- H1 BDA SDK：MrDefinition1999/bbk-h1-bda-sdk，提交
  `067fe072477861dfc8949d7b1a55279fb92d2548`，Apache-2.0，许可证保留在子模块内。
- 暂停菜单和触摸栏字形：Noto Sans CJK SC 子集，SIL OFL 1.1，
  `assets/licenses/NotoSansCJK-OFL.txt`。
- 游戏内字体按上游 `npe-sdl/assets/FONT-LICENSE.txt` 和 `FONT-PROVENANCE.txt` 保留来源说明。
  当前 NP560 原机字形不在原创源码 GPL 授权范围内；来源记录明确指出历史 Noto/OFL
  文本不适用于这些原生字库，不能将该文本视为原机字库的再分发授权。
- 应用图标：内置 imagegen 生成的学习机插画，设计与提示词见 `assets/README.md`。
  诺亚舟 NP560+ 外观和 H1 原生图标仅作为主体/风格参考；未直接复制照片或原机图标资源。
- `assets/screenshots/` 为独立 H1 V1.41 固件模拟器的实测帧缓冲，
  记录见 `docs/evidence/`；其中原生桌面资源和《天降风云》画面归原权利人。

本项目未包含、发布 NPE 游戏或原机固件；源码 GPL 授权不改变第三方资源的权利。
