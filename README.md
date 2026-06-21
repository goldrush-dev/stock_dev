# stock_bot - KIS 모의투자 자동매매 샘플

## 준비
```powershell
pip install requests pandas pyyaml
```

## 설정
`config_virtual.yaml`에 APP_KEY / APP_SECRET / CANO를 넣으세요.

## 실행
```powershell
py main.py
```

토요일/일요일 또는 장외 시간에는 주문이 거부될 수 있습니다.
