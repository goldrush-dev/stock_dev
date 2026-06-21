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

    def get_token(self):
        r = requests.post(
            self.base_url + "/oauth2/tokenP",
            headers={"content-type": "application/json"},
            json={
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "appsecret": self.app_secret,
            },
        )

        data = r.json()

        if r.status_code != 200 or "access_token" not in data:
            msg = f"토큰 발급 실패 : {data}"

            write_error(msg)

            raise RuntimeError(msg)

        self.token = data["access_token"]
        print("TOKEN OK")
        return self.token

    def _headers(self, tr_id):
        if not self.token:
            raise RuntimeError("token 없음. get_token() 먼저 호출하세요.")

        return {
            "content-type": "application/json",
            "authorization": f"Bearer {self.token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }

    def get_price(self, code):
        r = requests.get(
            self.base_url + "/uapi/domestic-stock/v1/quotations/inquire-price",
            headers=self._headers("FHKST01010100"),
            params={
                "fid_cond_mrkt_div_code": "J",
                "fid_input_iscd": code,
            },
        )

        data = r.json()

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

        r = requests.get(
            self.base_url + "/uapi/domestic-stock/v1/trading/inquire-balance",
            headers=self._headers(tr_id),
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

        data = r.json()

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
        r = requests.post(
            self.base_url + "/uapi/domestic-stock/v1/trading/order-cash",
            headers=self._headers(tr_id),
            json={
                "CANO": self.cano,
                "ACNT_PRDT_CD": self.acnt_prdt_cd,
                "PDNO": code,
                "ORD_DVSN": "00",
                "ORD_QTY": str(qty),
                "ORD_UNPR": str(price),
            },
        )

        data = r.json()

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

        r = requests.get(
            self.base_url + "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
            headers=self._headers("FHKST03010100"),
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": code,
                "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
                "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
                "FID_PERIOD_DIV_CODE": "D",
                "FID_ORG_ADJ_PRC": "1",
            },
        )

        data = r.json()

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

        prices.reverse()  # 오래된 날짜 → 최신 날짜

        return prices[-days:]