import os
import json
import time
import random
import requests

from logger import write_error
from datetime import datetime, timedelta


class KisApi:
    def __init__(self, config):
        self.config = config
        self.base_url = config["base_url"]
        self.app_key = config["app_key"]
        self.app_secret = config["app_secret"]
        self.cano = config["cano"]
        self.acnt_prdt_cd = config["acnt_prdt_cd"]
        self.mode = config.get("mode", "virtual")
        self.token = None

    def _tr_id(self, real_id, virtual_id):
        return virtual_id if self.mode == "virtual" else real_id

    def _token_file(self):
        return "token_virtual.json" if self.mode == "virtual" else "token_real.json"

    def _load_saved_token(self):
        path = self._token_file()

        if not os.path.exists(path):
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            token = data.get("access_token")
            expire_at = data.get("expire_at")

            if not token or not expire_at:
                return None

            expire_time = datetime.strptime(expire_at, "%Y-%m-%d %H:%M:%S")

            # 만료 5분 전이면 새로 받도록 처리
            if datetime.now() < expire_time - timedelta(minutes=5):
                self.token = token
                print("TOKEN 재사용 OK")
                return token

        except Exception as e:
            write_error("TOKEN_LOAD_ERROR", str(e))

        return None

    def _save_token(self, token):
        # 토큰은 보통 24시간이지만, 안전하게 23시간만 사용
        expire_at = datetime.now() + timedelta(hours=23)

        with open(self._token_file(), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "access_token": token,
                    "expire_at": expire_at.strftime("%Y-%m-%d %H:%M:%S"),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    def get_token(self, force=False):
        if not force:
            saved_token = self._load_saved_token()
            if saved_token:
                return saved_token

        # 토큰 발급은 1분 1회 제한이 있으므로 최대 2회만 천천히 시도
        for attempt in range(2):
            try:
                r = requests.post(
                    self.base_url + "/oauth2/tokenP",
                    headers={"content-type": "application/json"},
                    json={
                        "grant_type": "client_credentials",
                        "appkey": self.app_key,
                        "appsecret": self.app_secret,
                    },
                    timeout=10,
                )

                data = r.json()

                if r.status_code == 200 and "access_token" in data:
                    self.token = data["access_token"]
                    self._save_token(self.token)
                    print("TOKEN 신규 발급 OK")
                    return self.token

                msg = f"토큰 발급 실패 : {data}"
                write_error("TOKEN_ERROR", msg)

                # 1분당 1회 제한이면 65초 대기 후 한 번 더 시도
                if "EGW00133" in str(data) and attempt == 0:
                    print("토큰 발급 제한. 65초 후 재시도합니다.")
                    time.sleep(65)
                    continue

                raise RuntimeError(msg)

            except requests.exceptions.RequestException as e:
                write_error("TOKEN_REQUEST_ERROR", str(e))
                if attempt == 0:
                    time.sleep(5)
                    continue
                raise

        raise RuntimeError("토큰 발급 실패")

    def _headers(self, tr_id):
        if not self.token:
            self.get_token()

        return {
            "content-type": "application/json",
            "authorization": f"Bearer {self.token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }

    def _is_token_error(self, data):
        text = str(data)
        return (
            "EGW00123" in text
            or "EGW00121" in text
            or "기간이 만료" in text
            or "토큰" in text
            or "token" in text.lower()
            or "unauthorized" in text.lower()
        )

    def _is_rate_limit_error(self, data):
        text = str(data)
        return "EGW00215" in text or "초당 거래건수" in text

    def _request_once(self, method, url, tr_id=None, **kwargs):
        if tr_id:
            kwargs["headers"] = self._headers(tr_id)

        r = requests.request(method, url, timeout=10, **kwargs)

        try:
            data = r.json()
        except Exception:
            msg = f"JSON 변환 실패 : status={r.status_code}, text={r.text[:300]}"
            write_error("JSON_ERROR", msg)
            raise RuntimeError(msg)

        return r, data

    def _request(self, method, url, tr_id=None, retry=True, **kwargs):
        max_attempts = 3
        last_error = None

        for attempt in range(max_attempts):
            try:
                # 초당 제한 방지용 짧은 랜덤 대기
                if attempt == 0:
                    time.sleep(random.uniform(0.25, 0.6))

                r, data = self._request_once(method, url, tr_id=tr_id, **kwargs)

                # 토큰 만료/인증 오류 → 토큰 재발급 후 재시도
                if retry and (r.status_code in (401, 403) or self._is_token_error(data)):
                    print("토큰 만료/인증 오류 감지. 토큰 재발급 후 재시도합니다.")
                    write_error("TOKEN_RETRY", str(data))
                    self.get_token(force=True)
                    time.sleep(1.5)
                    continue

                # 초당 거래건수 초과 → 잠시 대기 후 재시도
                if retry and self._is_rate_limit_error(data):
                    wait_sec = 2 + attempt * 2
                    print(f"API 초당 제한 감지. {wait_sec}초 후 재시도합니다.")
                    write_error("RATE_LIMIT_RETRY", str(data))
                    time.sleep(wait_sec)
                    continue

                return r, data

            except requests.exceptions.RequestException as e:
                last_error = e
                wait_sec = 3 + attempt * 4
                write_error("REQUEST_ERROR", f"{e} / retry={attempt + 1}/{max_attempts}")

                if attempt < max_attempts - 1:
                    print(f"네트워크 오류. {wait_sec}초 후 재시도합니다.")
                    time.sleep(wait_sec)
                    continue

                raise

        if last_error:
            raise last_error

        raise RuntimeError("API 요청 실패")

    def get_price(self, code):
        _, data = self._request(
            "GET",
            self.base_url + "/uapi/domestic-stock/v1/quotations/inquire-price",
            tr_id="FHKST01010100",
            params={
                "fid_cond_mrkt_div_code": "J",
                "fid_input_iscd": code,
            },
        )

        if data.get("rt_cd") != "0":
            msg = f"현재가 조회 실패 : {data}"
            write_error(msg)
            raise RuntimeError(msg)

        output = data["output"]

        return {
            "price": int(output.get("stck_prpr", "0") or "0"),
            "diff": output.get("prdy_vrss", "-"),
            "rate": output.get("prdy_ctrt", "-"),
        }

    def get_balance(self):
        tr_id = self._tr_id("TTTC8434R", "VTTC8434R")

        _, data = self._request(
            "GET",
            self.base_url + "/uapi/domestic-stock/v1/trading/inquire-balance",
            tr_id=tr_id,
            params={
                "CANO": self.cano,
                "ACNT_PRDT_CD": self.acnt_prdt_cd,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "00",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            },
        )

        if data.get("rt_cd") != "0":
            msg = f"잔고 조회 실패 : {data}"
            write_error(msg)
            raise RuntimeError(msg)

        return data

    def buy(self, code, qty, price):
        tr_id = self._tr_id("TTTC0802U", "VTTC0802U")
        return self._order(code, qty, price, tr_id, "매수")

    def sell(self, code, qty, price):
        tr_id = self._tr_id("TTTC0801U", "VTTC0801U")
        return self._order(code, qty, price, tr_id, "매도")

    def _order(self, code, qty, price, tr_id, name):
        _, data = self._request(
            "POST",
            self.base_url + "/uapi/domestic-stock/v1/trading/order-cash",
            tr_id=tr_id,
            json={
                "CANO": self.cano,
                "ACNT_PRDT_CD": self.acnt_prdt_cd,
                "PDNO": code,
                "ORD_DVSN": "00",
                "ORD_QTY": str(qty),
                "ORD_UNPR": str(price),
            },
        )

        if data.get("rt_cd") == "0":
            print(f"{name} 주문 성공:", data.get("output", {}))
        else:
            msg = f"{name} 주문 실패 : code={code}, qty={qty}, price={price}, data={data}"
            print(msg)
            write_error(msg)

        return data

    def get_daily_prices(self, code, days=100):
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days * 2)

        _, data = self._request(
            "GET",
            self.base_url + "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
            tr_id="FHKST03010100",
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": code,
                "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
                "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
                "FID_PERIOD_DIV_CODE": "D",
                "FID_ORG_ADJ_PRC": "1",
            },
        )

        if data.get("rt_cd") != "0":
            msg = f"일봉 조회 실패 : {data}"
            write_error(msg)
            raise RuntimeError(msg)

        output = data.get("output2", [])

        prices = []
        for item in output:
            close_price = item.get("stck_clpr")
            if close_price:
                prices.append(int(close_price))

        prices.reverse()

        return prices[-days:]
