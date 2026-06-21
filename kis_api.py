import requests


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
            raise RuntimeError(f"토큰 발급 실패: {data}")

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
            raise RuntimeError(f"현재가 조회 실패: {data}")

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
            raise RuntimeError(f"잔고 조회 실패: {data}")

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
            print(f"{name} 주문 실패:", data)

        return data