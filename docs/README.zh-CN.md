<div align="center">
  <h1>DeltaXRDbench</h1>
  <p><strong>用于 X 射线衍射物相鉴定与精修的可复现基准</strong></p>
  <p>面向模拟与实验 XRD 数据集的模型无关评测，<br>通过隐藏参考 CIF 进行结构感知评分。</p>
  <p>
    <a href="https://www.python.org/"><img alt="Python 3.9+" src="https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&amp;logoColor=white"></a>
    <a href="https://github.com/Asterbin/xrdbench/releases"><img alt="数据集" src="https://img.shields.io/badge/Datasets-GitHub_Releases-2ea44f?logo=github"></a>
    <a href="https://asterbin.github.io/xrdbench/"><img alt="文档" src="https://img.shields.io/badge/Docs-GitHub_Pages-2563eb?logo=githubpages&amp;logoColor=white"></a>
    <a href="https://github.com/Asterbin/xrdbench/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/Asterbin/xrdbench?style=flat&amp;logo=github"></a>
  </p>
  <p><strong><a href="../README.md">English</a> · <a href="./README.zh-CN.md">中文</a> · <a href="./README.ja.md">日本語</a> · <a href="./README.ko.md">한국어</a></strong></p>
  <p><a href="https://asterbin.github.io/xrdbench/">入门指南</a> · <a href="https://github.com/Asterbin/xrdbench/releases">下载数据集</a> · <a href="../domo/README.md">提交格式</a> · <a href="../explore_datasets.ipynb">数据集笔记本</a></p>
</div>

---

## 项目概览

| 结构感知 | 模型无关 | 可复现 | 多模态 |
| :---: | :---: | :---: | :---: |
| 隐藏 CIF 匹配 | 支持任意模型或检索系统 | 固定清单与随机种子 | 纯 XRD 与 XRD + 成分信息 |

DeltaXRDbench 根据解析后的晶体结构评测预测结果，而不是比较 CIF 文件名或文本格式。它通过统一的 JSONL 接口支持单相候选排序、多相无序集合和谱图精修输出。

## 评测任务

| 任务 | 模型输入 | 隐藏参考 | 报告指标 |
| --- | --- | --- | --- |
| **单相鉴定** | XRD 或 XRD + 成分信息 | 一个参考 CIF | Top-1、Top-3、Top-5、MRR@5 |
| **多相鉴定** | 混合 XRD 或 XRD + 成分信息 | 2–3 个参考 CIF 构成的集合 | Coverage、Exact、宏平均 P/R/F1 |
| **精修** | 实验谱与计算谱 | 不需要结构真值 | Rp、Rwp、相关系数、XRDinspector 分数 |

每个多相样本包含两个或三个不同物相，且各物相比例均不低于 10%。纯 XRD 与 XRD + 成分信息使用相同的指标，并分别报告结果。

## 快速开始

### 1. 安装

```bash
git clone --recurse-submodules https://github.com/Asterbin/xrdbench.git
cd xrdbench
pip install -e ./XRDinspector -e .
```

### 2. 下载数据集

从 [GitHub Releases](https://github.com/Asterbin/xrdbench/releases) 下载数据集压缩包，然后解压到 `datasets/` 下，并保留 `mp500`、`rruff` 或 `opxrd` 目录名。

### 3. 评测提交结果

```bash
xrdbench dataset.jsonl submissions/model-a.jsonl \
  --data-root . \
  --output report.json
```

## 提交格式

JSONL 中的每条记录都将基准 `sample_id` 与模型输出对应起来。模型可以直接提交标准 CIF 文件，无需知道数据库内部的物相 ID。

```json
{"sample_id":"rruff-single-000000","prediction":{"structure_files":["predictions/rank-1.cif","predictions/rank-2.cif"]}}
```

- **单相：** 按排名顺序提交最多五个经过结构去重的 CIF。
- **多相：** 提交一个无序且经过结构去重的 CIF 集合。
- **显式空集合：** 作为零分预测参与评分。
- **省略样本：** 不进入条件平均，并降低多相 Coverage。

有关 CIF 路径、`pymatgen.Structure` 导出、旧版物相 ID 和输入校验的完整说明，请参阅[提交指南](../domo/README.md)。

<details>
<summary><strong>指标定义与汇总方法</strong></summary>

所有鉴定任务的汇总结果均以百分比表示。单相 Top-k 表示前 k 个候选中是否出现首个结构匹配，MRR@5 则对首次匹配名次的倒数取平均。候选排序与后处理必须在无法访问隐藏真值的情况下预先固定。

多相 Precision、Recall 和 F1 是在已评分混合物上的逐样本宏平均。Exact 要求预测集合与参考集合完全相同，Coverage 定义为 `100 × N_scored / N`。在 oracle 筛选设置下，如果某个混合物没有保留任何正比例候选，则将其排除在条件 P/R/F1 平均之外，并通过 Coverage 反映这种缺失。

评测器每次报告一个运行结果。基准表格中的数值是三个固定随机种子所得百分比结果的无权重平均。

</details>

## 数据集

| 数据集 | 谱图来源 | 单相样本 | 混合物 | 说明 |
| --- | --- | ---: | ---: | --- |
| **MP500** | 模拟 | 10,000 | 30,000 | Cu Kα；结构所含原子数不超过 100 |
| **RRUFF** | 实验 | 1,164 | 10,000 | 可用的结构–谱图对 |
| **opXRD** | 实验 | 880 | 10,000 | 可用的结构–谱图对 |

数据集压缩包作为 Release 附件发布，不会随 `git clone` 下载。有关数据文件布局与约定，请参阅 [datasets/README.md](../datasets/README.md)。

## 项目结构

```text
xrdbench/
├── xrdbench/          # 评测与数据集准备包
├── domo/              # 提交示例与辅助代码
├── tests/             # 评测器自动化测试
├── datasets/          # 下载的数据文件，不纳入 Git
└── XRDinspector/      # 固定版本的精修评分依赖
```

## 可复现性

数据集清单记录数据来源、谱图位置、隐藏参考 CIF 路径、内部审计 ID 和混合比例。正式发布的数据还应记录源数据快照、随机种子、预处理配置和 SHA-256 校验和。

## 许可证

数据源的许可证与署名要求仍由各自提供方规定。在公开再分发代码或数据文件之前，请先为本项目添加许可证。
