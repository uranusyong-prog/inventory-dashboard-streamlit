# 26년 부진·부동 재고 소진 대시보드 (Streamlit)

Google Sheets 데이터를 실시간으로 시각화하는 Streamlit 앱.

## 로컬 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud 배포

1. 이 폴더를 GitHub 저장소로 push
2. https://share.streamlit.io 접속 → "New app"
3. 저장소·브랜치·`app.py` 선택 → Deploy

## 시트 공개 설정 필요

앱이 시트를 읽으려면 시트가 "웹에 게시"되어 있어야 합니다.

1. Google Sheets에서 파일 → 공유 → 웹에 게시
2. 형식: CSV, 시트: 첫 번째 시트
3. 게시 → 완료

## 데이터 갱신

5분마다 자동 캐시 갱신. 즉시 갱신은 사이드바 "🔄 시트 새로고침" 버튼.
