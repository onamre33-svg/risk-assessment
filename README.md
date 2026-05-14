# 위험성평가 모바일 웹앱

현장 출입 전 위험성평가를 모바일에서 작성·승인하는 PWA(Progressive Web App).

## 주요 기능
- 마스터 / 팀 담당자 / 안전 관리자 / 엔지니어 4단계 권한
- 엔지니어 제출 → 팀 담당자 승인 / 반려 워크플로우
- 같은 팀 담당자, 안전 관리자, 마스터에게 자동 알림
- 모바일 최적화 + PWA 설치 (아이폰·갤럭시 모두 지원)
- 오프라인에서 작성 → 인터넷 복구 시 자동 제출

## 실행 방법 (VS Code 터미널)

```bash
# 1) 의존성 설치
pip install -r requirements.txt

# 2) 서버 실행
python app.py
```

서버가 시작되면 브라우저에서 접속:

- 같은 PC: `http://localhost:5000`
- 같은 와이파이의 휴대폰: `http://<PC의 IP>:5000`
  - Windows에서는 `ipconfig`, Mac/Linux는 `ifconfig` 로 IP 확인

## 테스트 계정

| 역할 | 아이디 | 비밀번호 | 비고 |
|------|--------|---------|------|
| 마스터 | admin | admin1234 | 전체 권한 |
| 팀담당자 | manager1 | 1234 | 전기팀 |
| 팀담당자 | manager2 | 1234 | 기계팀 |
| 안전관리자 | safety1 | 1234 | 모든 제출 열람 |
| 엔지니어 | eng1 | 1234 | 전기팀 |
| 엔지니어 | eng2 | 1234 | 기계팀 |

## 모바일에 설치하기 (PWA)

- 갤럭시 (안드로이드 크롬): 주소 접속 → 메뉴 → "홈 화면에 추가"
- 아이폰 (사파리): 주소 접속 → 공유 버튼 → "홈 화면에 추가"

## 폴더 구조

```
risk_app/
├── app.py              # Flask 메인 (라우트, DB, 인증)
├── requirements.txt
├── data.db             # 첫 실행시 자동 생성
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── form.html
│   ├── submission_detail.html
│   ├── notifications.html
│   ├── users.html
│   └── teams.html
└── static/
    ├── style.css
    ├── app.js          # PWA 등록, 오프라인 큐
    ├── sw.js           # 서비스 워커
    ├── manifest.json
    ├── icon-192.png
    └── icon-512.png
```

## 데이터 모델 (SQLite)

- `users` (id, username, password, name, role, team_id, phone, email)
- `teams` (id, name, created_at)
- `submissions` (id, engineer_id, team_id, status, data_json, reviewer_id, reviewed_at, rejection_reason, created_at)
- `notifications` (id, user_id, message, link, is_read, created_at)

## 다음 단계 (확장 아이디어)

- 카카오 알림톡 / 이메일 / 푸시 알림 연동
- 사진 첨부 (현장 사진 업로드)
- PDF 출력 (감사용)
- 통계 대시보드 (월별 제출 건수, 자주 발생하는 위험 항목 등)
- 다국어 (영어) 지원

---
문의 / 수정 사항은 언제든 알려주세요.
