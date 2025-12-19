# TransSRT Deployment Guide

## Prerequisites

1. **Google Cloud SDK (gcloud)** installed and configured
2. **Google Cloud Project** created
3. **Billing enabled** on your project
4. **Required APIs enabled**:
   - Cloud Functions API
   - Cloud Build API
   - Secret Manager API
5. **PowerShell** (Windows 기본 제공)

## Configuration

모든 설정은 `.env` 파일에서 관리됩니다:

```bash
# Gemini API Configuration
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-pro

# Translation Settings
CHUNK_SIZE=100
MAX_CONCURRENT_REQUESTS=5
MAX_FILE_SIZE_MB=10

# CORS Settings
CORS_ORIGINS=*
```

### 설정 옵션

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `GEMINI_API_KEY` | *필수* | Google AI Studio에서 발급받은 Gemini API 키 |
| `GEMINI_MODEL` | `gemini-2.5-pro` | 사용할 Gemini 모델 (gemini-2.5-pro 권장) |
| `CHUNK_SIZE` | `100` | 청크당 자막 엔트리 개수 |
| `MAX_CONCURRENT_REQUESTS` | `5` | 최대 동시 API 요청 수 (1-10) |
| `MAX_FILE_SIZE_MB` | `10` | 최대 업로드 파일 크기 (MB) |
| `CORS_ORIGINS` | `*` | CORS 오리진 (공개 접근은 `*` 사용) |

### 모델 권장사항

- **gemini-2.5-pro**: 높은 rate limit (권장), 좋은 품질
- **gemini-1.5-flash**: 가장 빠름, 저렴, 테스트용으로 좋음
- **gemini-3-pro-preview**: 매우 엄격한 rate limit, 동시 요청 비권장

## 배포 방법

### PowerShell에서 배포 (Windows)

1. PowerShell을 관리자 권한으로 실행
2. `backend` 폴더로 이동
3. 배포 스크립트 실행:

```powershell
cd backend
.\deploy.ps1
```

### 스크립트가 하는 일

1. ✅ `.env` 파일 검증
2. ✅ Google Cloud Secret에 API 키 생성/업데이트
3. ✅ `.env`에서 환경 변수를 읽어 Cloud Function 배포
4. ✅ 배포 성공 확인
5. ✅ 배포된 설정이 `.env`와 일치하는지 검증

### 예상 출력

```
=========================================
TransSRT Deployment Script
=========================================

Loading configuration from .env...

Deployment Configuration:
  GEMINI_MODEL: gemini-2.5-pro
  CHUNK_SIZE: 100
  MAX_CONCURRENT_REQUESTS: 5
  MAX_FILE_SIZE_MB: 10
  CORS_ORIGINS: *

Updating Google Cloud Secret Manager...
Secret exists, updating to latest version...
[SUCCESS] Secret updated successfully

Deploying Cloud Function...
Creating .env.yaml from .env...
[Build]...done
[Service]...done

=========================================
[SUCCESS] Deployment successful!
=========================================

Function URL: https://translate-srt-xxx.a.run.app

Verifying deployed configuration...
  Deployed GEMINI_MODEL: gemini-2.5-pro
  Deployed MAX_CONCURRENT_REQUESTS: 5
  Deployed CHUNK_SIZE: 100

[SUCCESS] All checks passed!
```

## Troubleshooting

### 문제: "GEMINI_API_KEY not set in .env"
**해결**: `.env` 파일이 존재하고 유효한 API 키가 포함되어 있는지 확인하세요.

### 문제: "gcloud: command not found"
**해결**:
1. Google Cloud SDK가 설치되어 있는지 확인
2. PowerShell을 다시 시작
3. `gcloud --version`으로 설치 확인

### 문제: Rate Limit 에러 (429)
**해결방법**:
- `MAX_CONCURRENT_REQUESTS`를 줄이기 (3 또는 1로)
- `gemini-2.5-pro` 모델로 변경 (10배 높은 limit)
- 재시도 전 몇 분 대기

### 문제: 배포가 멈추거나 실패
**해결방법**:
- 인터넷 연결 확인
- `gcloud` 인증 확인: `gcloud auth list`
- 프로젝트 설정 확인: `gcloud config get-value project`
- 필요한 API 활성화:
  ```powershell
  gcloud services enable cloudfunctions.googleapis.com
  gcloud services enable cloudbuild.googleapis.com
  gcloud services enable secretmanager.googleapis.com
  ```

### 문제: 배포된 설정이 .env와 다름
**해결**: 스크립트가 경고를 표시합니다. 이 경우:
1. 출력의 경고 확인
2. 배포 스크립트 재실행
3. 배포 중 `.env` 파일이 변경되지 않았는지 확인

## 수동 배포

스크립트 없이 수동으로 배포하려면:

```powershell
# Secret 업데이트
echo "YOUR_API_KEY" | gcloud secrets versions add GEMINI_API_KEY --data-file=-

# .env.yaml 생성
@"
MAX_CONCURRENT_REQUESTS: '5'
CHUNK_SIZE: '100'
GEMINI_MODEL: 'gemini-2.5-pro'
MAX_FILE_SIZE_MB: '10'
CORS_ORIGINS: '*'
"@ | Out-File -FilePath ".env.yaml" -Encoding UTF8

# 함수 배포
gcloud functions deploy translate-srt `
  --gen2 `
  --runtime=python311 `
  --region=us-central1 `
  --source=. `
  --entry-point=translate_srt `
  --trigger-http `
  --allow-unauthenticated `
  --set-secrets=GEMINI_API_KEY=GEMINI_API_KEY:latest `
  --env-vars-file=.env.yaml `
  --timeout=540s `
  --memory=512MB

# 정리
Remove-Item ".env.yaml"
```

## 로그 확인

### 최근 로그
```powershell
gcloud functions logs read translate-srt --region=us-central1 --gen2 --limit=50
```

### 실시간 로그
```powershell
gcloud functions logs tail translate-srt --region=us-central1 --gen2
```

### 에러만 필터링
```powershell
gcloud functions logs read translate-srt --region=us-central1 --gen2 --limit=100 | Select-String "ERROR"
```

## 비용 예상

일반적인 사용 기준:
- **Cloud Functions**: ~$0.0000004 per invocation + 컴퓨팅 시간
- **Gemini API**: 무료 티어에 넉넉한 할당량 포함, 이후 사용량 기반 과금
- **Secret Manager**: 활성 시크릿 버전 6개까지 무료

하루 100회 번역 기준 예상 비용: **월 $1 미만**

## 보안 참고사항

- API 키는 Google Secret Manager에 암호화되어 저장
- `--allow-unauthenticated` 제거하면 인증 필요하도록 변경 가능
- `.env`의 `CORS_ORIGINS` 변경으로 CORS 제한 가능
- `.env` 파일은 절대 Git에 커밋하지 마세요 (이미 .gitignore에 포함됨)

## GitHub Actions 자동 배포

`main` 브랜치에 푸시하면 자동으로 배포됩니다:

1. `.github/workflows/deploy-backend.yml` 파일이 자동 배포 처리
2. GitHub Secrets에 `GCP_SA_KEY` 설정 필요
3. 수동 배포와 동일한 설정 사용

자동 배포를 비활성화하려면 workflow 파일을 삭제하거나 이름을 변경하세요.

## 지원

문제 발생 시 로그를 먼저 확인하세요:
```powershell
gcloud functions logs read translate-srt --region=us-central1 --gen2 --limit=100
```

주요 로그 메시지:
- `Rate limit exceeded: 429` → MAX_CONCURRENT_REQUESTS 줄이기
- `Expected X translations, got Y` → Gemini API 응답 품질 확인
- `Translation error (no retry)` → 파싱 실패, 프롬프트/응답 형식 확인
- `Detected format: sbv` → SBV 파일이 정상적으로 감지됨
- `Detected format: srt` → SRT 파일이 정상적으로 감지됨
