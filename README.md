# 스타포스 시뮬레이터 / Audit 대시보드

FastAPI 기반 프로젝트로, 두 가지를 제공합니다.

- **시뮬레이터**: "공정(Random) 뽑기" vs "블록(뭉침) 뽑기" 비교 (`/`)
- **Audit 대시보드**: `audit_data/*.json` 통계 분석/시각화 (`/audit`)

## 실행 (개발)

PowerShell:

```powershell
.\run_dev.ps1
```

CMD:

```bat
run_dev.bat
```

기본 접속: `http://127.0.0.1:8000`

포트 변경:

```powershell
.\run_dev.ps1 -Port 9000
```

```bat
run_dev.bat 9000
```

## 수동 실행

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 참고

- 실제 앱 엔트리는 `app/main.py`의 `app` 입니다.
- 루트의 `main.py`는 실험/레거시 코드로 보이며, 기본 실행 대상으로는 `app.main:app`를 권장합니다.

