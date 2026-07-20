# XRDBench

[![GitHub stars](https://img.shields.io/github/stars/Asterbin/xrdbench?style=social)](https://github.com/Asterbin/xrdbench/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/Asterbin/xrdbench?style=social)](https://github.com/Asterbin/xrdbench/network/members)

**面向 X 射线衍射相识别与精修结果的可复现评测基准。**

[English](../README.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md)

新手请先阅读：[完整中文 HTML 使用说明](GETTING_STARTED.zh-CN.html)

## 评测内容

| 任务 | 输入 | 真解 | 指标 |
| --- | --- | --- | --- |
| 单相识别 | 一条 XRD 谱图 | 一个隐藏真解 CIF | CIF 结构匹配 / 完全匹配 |
| 多相识别 | 一条混合 XRD 谱图 | 2–3 个隐藏真解 CIF | Precision、Recall、F1、完全匹配 |
| 精修 | 实验谱和计算谱 | 不要求结构真解 | Rp、Rwp、相关系数、XRDinspector 分数 |

所有多相样本包含 2 或 3 个不同相，且每个相的比例均不低于 10%。

## 目录结构

```text
xrdbench/
├── xrdbench/          # 评测与数据处理包
├── tests/             # 自动化测试
├── datasets/          # 生成的数据产物（Git 忽略）
└── XRDinspector/      # 固定版本的上游精修评分依赖
```

原始数据和大型 HDF5 结果不进入 Git 历史；规范见 [datasets/README.md](../datasets/README.md)。

## 下载数据集

数据集以 GitHub Release 附件发布，**不会**随 `git clone` 下载。

[![从 Releases 下载](https://img.shields.io/badge/数据集-GitHub%20Releases-2ea44f?logo=github)](https://github.com/Asterbin/xrdbench/releases)

请从 [Releases 页面](https://github.com/Asterbin/xrdbench/releases) 下载所需数据包，解压到 `datasets/`，并保留目录名：`mp500`、`rruff`、`opxrd`。

## 安装与运行

```bash
pip install -e ./XRDinspector -e .
xrdbench dataset.jsonl submissions/model-a.jsonl --output report.json
```

模型接口为 JSONL，因此传统检索程序、深度学习模型和 agent 都可以接入。推荐模型提交标准 CIF 文件路径；评测器解析 CIF 并与隐藏真解结构核对，模型无需知道 RRUFF 或 MP 的内部 ID。

```json
{"sample_id":"rruff-single-000000","prediction":{"structure_files":["predictions/result.cif"]}}
```

## 数据来源

| 来源 | 类型 | 目标内容 |
| --- | --- | --- |
| MP500 | 模拟 | 10,000 单相 Cu Kα 谱和 30,000 混相谱；结构原子数 ≤100 |
| RRUFF | 实验 | 1,282 个可用单相结构–谱图对及 10,000 混相谱 |
| opXRD | 实验 | 880 个可用单相结构–谱图对及 10,000 混相谱 |

## 可复现性

清单记录来源、谱图位置、隐藏真解 CIF 路径、内部审计 ID 与混相比例。发布数据版本时还应记录数据源快照、随机种子、预处理配置与 SHA-256 校验和。
