# XRDBench

[![GitHub stars](https://img.shields.io/github/stars/Asterbin/xrdbench?style=social)](https://github.com/Asterbin/xrdbench/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/Asterbin/xrdbench?style=social)](https://github.com/Asterbin/xrdbench/network/members)

**X선 회절 상 식별 및 정련 결과를 위한 재현 가능한 벤치마크입니다.**

[English](https://github.com/Asterbin/xrdbench/blob/main/README.md) · [简体中文](https://github.com/Asterbin/xrdbench/blob/main/docs/README.zh-CN.md) · [日本語](https://github.com/Asterbin/xrdbench/blob/main/docs/README.ja.md) · [한국어](https://github.com/Asterbin/xrdbench/blob/main/docs/README.ko.md)

## 평가 항목

| 작업 | 입력 | 정답 | 지표 |
| --- | --- | --- | --- |
| 단일상 식별 | XRD 패턴 1개 | 비공개 기준 CIF 1개 | CIF 구조 매칭 / 완전 일치 |
| 다상 식별 | 혼합 XRD 패턴 1개 | 비공개 기준 CIF 2–3개 | Precision, Recall, F1, 완전 일치 |
| 정련 | 실험 및 계산 패턴 | 구조 정답 불필요 | Rp, Rwp, 상관계수, XRDinspector 점수 |

모든 다상 샘플은 서로 다른 2개 또는 3개 상으로 구성되며, 각 상의 비율은 10% 이상입니다.

## 저장소 구조

```text
xrdbench/
├── xrdbench/          # 평가 및 데이터 생성 패키지
├── tests/             # 자동화 테스트
├── datasets/          # 생성 데이터 아티팩트(Git 제외)
└── XRDinspector/      # 고정된 업스트림 점수화 의존성
```

## 설치 및 실행

```bash
pip install -e ./XRDinspector -e .
xrdbench dataset.jsonl submissions/model-a.jsonl --output report.json
```

모델은 내부 상 ID 대신 표준 CIF 경로를 JSONL로 제출할 수 있습니다. XRDBench는 예측 CIF를 해석하여 비공개 기준 구조와 비교합니다.

## 데이터셋 다운로드

데이터셋은 GitHub Releases 자산으로 배포되며 `git clone`에 포함되지 않습니다.

[![Releases에서 다운로드](https://img.shields.io/badge/Datasets-GitHub%20Releases-2ea44f?logo=github)](https://github.com/Asterbin/xrdbench/releases)

[Releases 페이지](https://github.com/Asterbin/xrdbench/releases)에서 필요한 아카이브를 내려받아 `datasets/mp500/`, `datasets/rruff/`, `datasets/opxrd/`에 각각 압축 해제하세요.

## 데이터 소스

| 소스 | 유형 | 내용 |
| --- | --- | --- |
| MP500 | 시뮬레이션 | 단일상 Cu Kα 패턴 10,000개 및 혼합 패턴 30,000개(원자 수 ≤100) |
| RRUFF | 실험 | 사용 가능한 단일상 구조–패턴 쌍 1,164개 및 혼합 패턴 10,000개 |
| opXRD | 실험 | 사용 가능한 단일상 구조–패턴 쌍 880개 및 혼합 패턴 10,000개 |

매니페스트에는 상 라벨, 소스, 패턴 위치 및 혼합 비율이 저장됩니다. 공개 데이터 버전에는 소스 스냅샷, 난수 시드, 전처리 설정 및 SHA-256 체크섬도 기록해야 합니다.
