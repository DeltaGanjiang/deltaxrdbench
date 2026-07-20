# XRDBench 新手使用说明

XRDBench 是一个用于评测 XRD 模型结果的项目。它不限制模型类型：传统检索程序、深度学习模型、LLM agent，或你自己写的规则程序都可以接入。模型只需要读取谱图并输出规定格式的 JSONL 文件，XRDBench 负责统一打分和生成报告。

[English](../README.md) · [简体中文](GETTING_STARTED.zh-CN.md) · [项目中文简介](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md)

需要直接在浏览器阅读？打开 [HTML 版本](GETTING_STARTED.zh-CN.html)。

## 1. 你会得到什么

项目包含三类数据来源，每类都分为单相和多相识别样本：

| 数据集 | 类型 | 单相 | 多相 |
| --- | --- | --- | --- |
| MP500 | 模拟 Cu Kα XRD | 10,000 个结构–谱图对 | 30,000 个 2–3 相混合谱 |
| RRUFF | 实验 XRD | 有晶体结构标签的实验谱 | 10,000 个混合谱 |
| opXRD | 实验 XRD | 有晶体结构标签的实验谱 | 10,000 个混合谱 |

多相样本的每个相都占至少 10%，且最多三个相。也就是说，标签中有 `K` 个 phase ID，就代表该谱图由 `K` 个晶相混合而成。

项目也支持精修评测：输入实验谱和模型/精修程序导出的计算谱，使用 XRDinspector 输出 `Rp`、`Rwp`、相关系数和连续质量分数。

## 2. 第一次安装

### 2.1 获取代码

```bash
git clone --recurse-submodules https://github.com/Asterbin/xrdbench.git
cd xrdbench
```

如果克隆时忘记加 `--recurse-submodules`，运行：

```bash
git submodule update --init --recursive
```

### 2.2 创建 Python 环境

建议 Python 3.9 或更高版本。下面以 conda 为例：

```bash
conda create -n xrdbench python=3.11 -y
conda activate xrdbench
pip install -e ./XRDinspector -e .
```

确认命令可用：

```bash
xrdbench --help
xrdbench-prepare --help
```

如果系统没有把命令加入 PATH，也可使用：

```bash
python -m xrdbench.cli --help
python -m xrdbench.prepare --help
```

## 3. 下载数据集

数据集很大，因此不放在 Git 仓库中。请进入 [XRDBench Releases](https://github.com/Asterbin/xrdbench/releases)，下载需要的数据包并解压到仓库的 `datasets/` 下。

解压后目录应类似：

```text
xrdbench/
├── datasets/
│   ├── mp500/
│   │   ├── patterns.h5
│   │   ├── manifest.jsonl
│   │   └── structures/
│   ├── rruff/
│   └── opxrd/
├── xrdbench/
└── XRDinspector/
```

若你只想先跑通流程，建议先下载 RRUFF 或 opXRD；它们体积通常比 MP500 小。Release 页面应同时提供数据版本、来源、随机种子、校验和和许可信息；请在训练或发表结果时记录所用版本。

## 4. 数据文件怎么读

每个数据集目录包含三个部分：

| 文件/目录 | 用途 |
| --- | --- |
| `patterns.h5` | 所有标准化 XRD 向量和公共 2θ 网格 |
| `manifest.jsonl` | 每个样本的位置、任务类型、相标签、混合比例和元数据 |
| `structures/` | 单相样本的参考 CIF 文件 |

谱图被统一插值为 10–80° 2θ、步长 0.01°，因此每条谱图长度为 7,001。强度经过基线处理和面积归一化。实验数据在原始扫描范围之外补零。

### 4.1 最小读取示例

```python
import json
from pathlib import Path

import h5py

dataset_dir = Path("datasets/rruff")
record = json.loads((dataset_dir / "manifest.jsonl").read_text().splitlines()[0])

with h5py.File(dataset_dir / record["input"]["archive"], "r") as h5:
    two_theta = h5["two_theta_deg"][:]
    intensity = h5[record["input"]["dataset"]][record["input"]["index"]]

print(record["sample_id"])
print(record["task"])
print(two_theta.shape, intensity.shape)  # (7001,), (7001,)
```

单相记录的标签格式：

```json
"ground_truth": {"phase_ids": ["RRUFF:R120044"]}
```

多相记录的标签格式：

```json
"ground_truth": {"phase_ids": ["RRUFF:R120044", "RRUFF:R040120"]}
```

`metadata.fractions` 保存混合时的比例，便于审计；它不是当前识别任务的必交预测项。

> 测试集的 `ground_truth` 不能交给模型。实际发布测试时，应只给模型 `sample_id`、输入谱图和允许使用的元数据；真解保留在评测端。

## 5. 让你的模型接入

你的模型不需要继承类，也不需要调用特定 SDK。完成推理后，写一个 UTF-8 的 JSONL 文件：一行一个样本。

### 5.1 单相预测

```json
{"sample_id":"rruff-single-000000","prediction":{"phase_ids":["RRUFF:R120044"]}}
```

单相任务必须且只能提交一个 phase ID。

### 5.2 多相预测

```json
{"sample_id":"rruff-multi-000000","prediction":{"phase_ids":["RRUFF:R120044","RRUFF:R040120"]}}
```

多相 phase ID 是无序集合。多报相会降低 precision，漏报相会降低 recall；完全一致才算 `exact_match`。

### 5.3 最小提交文件

创建 `submission.jsonl`：

```text
{"sample_id":"rruff-single-000000","prediction":{"phase_ids":["RRUFF:R120044"]}}
{"sample_id":"rruff-multi-000000","prediction":{"phase_ids":["RRUFF:R120044","RRUFF:R040120"]}}
```

不要重复 `sample_id`。未提交的样本被记为 `missing_prediction`，并按零分计入汇总，避免只提交容易样本造成分数虚高。

## 6. 运行识别评测

评测命令接收两个 JSONL：评测端数据集清单和模型提交清单。

```bash
xrdbench path/to/evaluation-dataset.jsonl submission.jsonl --output report.json
```

输出 `report.json` 中有两层内容：

```json
{
  "summary": {
    "identification.single": {
      "exact_match_rate": 0.91,
      "macro_f1": 0.91,
      "coverage": 1.0
    },
    "identification.multi": {
      "exact_match_rate": 0.52,
      "macro_precision": 0.80,
      "macro_recall": 0.73,
      "macro_f1": 0.75
    }
  },
  "samples": []
}
```

- `summary`：排行榜和总览使用的聚合指标。
- `samples`：逐样本结果，用于分析具体在哪些谱图上漏相、误报或失败。
- `coverage`：完成预测的样本比例。
- `exact_match_rate`：预测相集合与真解完全相同的比例。
- `macro_f1`：先算每个样本 F1，再取平均；不会让大相或易样本主导结果。

## 7. 精修评测

精修不要求已知“唯一正确结构”。你需要提供实验谱和模型导出的计算谱，均为两列文本：

```text
two_theta_deg intensity
10.00  123.4
10.01  125.8
```

直接评测一对谱图：

```bash
xrdinspector refine experimental.xy calculated.xy
```

或在 XRDBench JSONL 提交中写：

```json
{"sample_id":"refine-001","prediction":{"calculated_pattern":"outputs/refine-001.xy"}}
```

评测报告包括：

- `Rp`：绝对残差因子，越低越好；
- `Rwp`：加权残差因子，越低越好；
- `correlation`：实验谱和计算谱的形状相关性，越接近 1 越好；
- `score`：0–100 的连续质量分数；
- `reasonable`：当前默认阈值下的可用标记。

这些指标反映谱图拟合一致性，不能单独证明结构在化学或晶体学上正确。仍应检查差谱、参数不确定度、相分数和结构合理性。

## 8. 自己重建数据集（高级）

如果你拥有原始数据库，可用以下命令重建。生成的数据默认不进入 Git，请通过 Release、对象存储或 DOI 归档发布。

```bash
# RRUFF 实验谱：全部可用单相 + 10,000 混合谱
xrdbench-prepare rruff RRUFF.db datasets/rruff --mixtures 10000 --seed 20260720

# MP500：随机选 10,000 个原子数不超过 100 的结构，再生成 30,000 混合谱
xrdbench-prepare mp500 MP500.db datasets/mp500 \
  --single-count 10000 --mixtures 30000 --seed 20260720

# opXRD JSON 数据
xrdbench-prepare opxrd-json opxrd datasets/opxrd --mixtures 10000 --seed 20260720
```

`--seed` 固定随机选择、峰形扰动和混相比例。相同数据源、参数和 seed 应得到同一份数据版本。

## 9. 常见问题

### 找不到 `xrdbench` 命令

确认已经激活安装环境，并重新安装：

```bash
pip install -e ./XRDinspector -e .
```

也可暂时使用 `python -m xrdbench.cli`。

### `patterns.h5` 找不到

数据集不随 Git clone 下载。请从 [Releases](https://github.com/Asterbin/xrdbench/releases) 下载，解压到 `datasets/`。

### 模型输出了 CIF，为什么还要 phase ID？

同一结构可能有不同 CIF 排版、origin choice 或 cell setting，直接比较 CIF 文本会误判。评测使用稳定、可追溯的 canonical phase ID，例如 `MP:mp-123` 或 `RRUFF:R120044`。如需保留模型 CIF，可把它另存为附加结果。

### 能否训练集、验证集、测试集混用？

不建议。先固定 split；来自同一原始样本或近重复谱图必须进入同一个 split，避免数据泄漏。公开测试集真解应始终保留在评测端。

## 10. 下一步

1. 下载一个 Release 数据包并用第 4 节代码成功读取一条谱图。
2. 让模型为少量样本写出 `submission.jsonl`。
3. 在验证集运行第 6 节评测命令，先确认接口和标签命名空间正确。
4. 再运行完整测试集，并保存 `report.json`、模型版本、数据版本和随机种子。

遇到数据版本、标签或接口问题，请在 [GitHub Issues](https://github.com/Asterbin/xrdbench/issues) 中附上所用 Release 版本、命令和完整错误信息。
