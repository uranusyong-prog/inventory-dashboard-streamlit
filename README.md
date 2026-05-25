# 26년 부진·부동 재고 소진 대시보드 (Streamlit)

Google Sheets 데이터를 실시간으로 시각화하는 Streamlit 앱.

## 로컬 실행

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Streamlit Cloud 배포

1. 이 폴더를 GitHub 저장소로 push
2. https://share.streamlit.io 접속 → "New app"
3. 저장소·브랜치 선택, Main file path는 `streamlit_app.py` → Deploy

## 시트 공개 설정 (필수)

앱이 시트를 읽으려면 시트가 "웹에 게시"되어 있어야 합니다.

1. Google Sheets에서 파일 → 공유 → 웹에 게시
2. 형식: CSV, 시트: 첫 번째 시트
3. 게시 → 완료

## 데이터 갱신

매일 한국시간(KST) 자정 기준으로 캐시가 자동 무효화됩니다.
- 자정 이후 