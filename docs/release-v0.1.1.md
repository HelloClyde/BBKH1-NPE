# 诺亚舟NPE v0.1.1（预发布）

本次补齐上游 NPE 引擎的 GPL-2.0 授权，并更新 H1 项目的固定子模块。

- NPE 上游原创源码已由项目所有者按 GPL-2.0-only 授权，根目录含 `LICENSE` 和 `NOTICE.md`。
- H1 固定 NPE 提交更新为 `7e156527d2d668b666fc203df2aadb929ab83de1`。
- 安装包新增上游许可证及来源说明，完整源码包包含带许可证的固定依赖。
- README 与 NOTICE 更新许可范围；SDK、字体及游戏画面的独立来源保持明确。

此次上游仅更新 LICENSE、NOTICE 和 README，没有修改引擎代码。
正式 BDA 与 v0.1.0 逐字节一致，SHA256：
`61663b93ff028da42213c3b137c891c4c6577efb3e5cabbbe48b7c4a95e7ba63`。
H1 SDK 保持 `067fe072477861dfc8949d7b1a55279fb92d2548`。

下载 `BBKH1-NPE-v0.1.1-install.zip`，把 `应用`、`NPE` 两个目录合并到 H1 的 A 盘。
保留两个 GBK 字体，游戏文件自行提供。安装包内 BDA 文件名仍为 `H1NPE.bda`。
提供完整源码 ZIP、构建/验证记录及 `SHA256SUMS.txt`。

沿用不变 BDA 的真实 MIPS 及完整 H1 固件模拟器证据，CI 检查精确摘要和退出路径。
未真机验证；完整剧情、跨游戏兼容和长期音频稳定性仍待验证，此前观察到一次音频欠载。
游戏、固件未打包。GPL 源码授权不包含原机字形与游戏画面，范围见两项目的 NOTICE。
