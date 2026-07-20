# XRDBench

[![GitHub stars](https://img.shields.io/github/stars/Asterbin/xrdbench?style=social)](https://github.com/Asterbin/xrdbench/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/Asterbin/xrdbench?style=social)](https://github.com/Asterbin/xrdbench/network/members)

**X 線回折の相同定・リファインメント結果のための再現可能なベンチマークです。**

[English](../README.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md)

## 評価対象

| タスク | 入力 | 正解 | 指標 |
| --- | --- | --- | --- |
| 単相同定 | 1 本の XRD パターン | 非公開の参照 CIF 1 つ | CIF 構造照合 / 完全一致 |
| 多相同定 | 混合 XRD パターン | 非公開の参照 CIF 2–3 個 | Precision、Recall、F1、完全一致 |
| リファインメント | 実験・計算パターン | 構造正解は不要 | Rp、Rwp、相関、XRDinspector score |

多相サンプルは 2 または 3 の異なる相で構成され、各相の割合は 10% 以上です。

## 構成

```text
xrdbench/
├── xrdbench/          # 評価・データ作成パッケージ
├── tests/             # 自動テスト
├── datasets/          # 生成済みデータ（Git 管理外）
└── XRDinspector/      # 固定された上流スコアリング依存関係
```

## インストールと実行

```bash
pip install -e ./XRDinspector -e .
xrdbench dataset.jsonl submissions/model-a.jsonl --output report.json
```

モデルは内部相 ID ではなく標準 CIF のパスを JSONL に出力できます。XRDBench は予測 CIF を解析し、非公開の参照構造と照合します。

## データセットのダウンロード

データセットは GitHub Releases のアセットとして配布され、`git clone` には含まれません。

[![Releases からダウンロード](https://img.shields.io/badge/Datasets-GitHub%20Releases-2ea44f?logo=github)](https://github.com/Asterbin/xrdbench/releases)

[Releases ページ](https://github.com/Asterbin/xrdbench/releases)から必要なアーカイブを取得し、`datasets/mp500/`、`datasets/rruff/`、`datasets/opxrd/` として展開してください。

## データソース

| ソース | 種類 | 内容 |
| --- | --- | --- |
| MP500 | シミュレーション | 10,000 単相 Cu Kα パターンと 30,000 混合パターン（原子数 ≤100） |
| RRUFF | 実験 | 使用可能な単相構造–パターン対 1,164 件と 10,000 混合パターン |
| opXRD | 実験 | 使用可能な単相構造–パターン対 880 件と 10,000 混合パターン |

マニフェストには相ラベル、ソース、パターン位置、混合比率が保存されます。公開版ではソースのスナップショット、乱数シード、前処理設定、SHA-256 も記録してください。
