import requests
import ast

from main import get_request_mpstats, get_request_create_history_price


class OdooAuth:
    def __init__(self):
        self.db = "db_odoo"
        self.username = "admin"
        self.password = "TyXdcirZQYQp5r7"
        self.url = "http://0.0.0.0:8070/"

    def connect_to_odoo_api_with_auth(self) -> dict:
        session_url = f"{self.url}/web/session/authenticate"
        data = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "db": self.db,
                "login": self.username,
                "password": self.password,
            },
        }
        session_response = requests.post(session_url, json=data)
        session_data = session_response.json()

        if session_data.get("result") and session_response.cookies.get("session_id"):
            session_id = session_response.cookies["session_id"]
            headers = {"Cookie": f"session_id={session_id}"}
            return headers
        else:
            print(f'Error: Failed to authenticate - {session_data.get("error")}')
            return None


class ParsingMPStats(OdooAuth):
    def __init__(self):
        super().__init__()
        self.chunk_size = 1000
        self.cache_dir = "./cache"

    def send_to_celery_and_wait_result(self, list_sku, token_mp_stats):
            results = []

            for sku in list_sku:
                result = get_request_mpstats.delay(token_mp_stats, sku)
                results.append(result)

            for result in results:
                try:
                    result.get(timeout=None)
                except Exception as e:
                    raise Exception(f"Ошибка при импорте файла: {e}")
                
    def get_request_count_competitors(self, path: str) -> int:
        endpoint = f"{self.url}{path}"
        headers = self.connect_to_odoo_api_with_auth()

        response = requests.get(endpoint, headers=headers)

        if response.status_code != 200:
            raise Exception("Can't get data from odoo about count competitors!")
        
        r_json = response.json()
        return r_json["total_records"]
    
    def _get_token_mpstats(self) -> str:
        headers = self.connect_to_odoo_api_with_auth()
        url = "http://0.0.0.0:8070/get_settings_credentials"
        response = requests.post(url, headers=headers)
        if response.status_code == 200:
            r_json = response.json()
            token_mpstats = r_json.get("MP_STATS_TOKEN")
            if not token_mpstats:
                raise Exception("MPStats токен не задан в ozon.settings")
        return token_mpstats

    def _get_request_sku_competitors(self, path: str, range: int) -> requests.Response:
        endpoint = f"{self.url}{path}"
        headers = self.connect_to_odoo_api_with_auth()

        data = {"range": range}
        response = requests.post(endpoint, headers=headers, data=data)

        if response.status_code != 200:
            return response

        answer = response.json()
        product_competitors_list = answer["product_competitors"]
        return product_competitors_list
    
    def create_chunks(self, count_sku) -> int:
        num_chunks = count_sku // self.chunk_size
        num_chunks = num_chunks + 1
        return num_chunks

    def main(self):
        token_mp_stats = self._get_token_mpstats()

        count_sku = self.get_request_count_competitors(
            path="/api/v1/price_history_competitors/count_records/"
        )
        
        num_chunks = self.create_chunks(count_sku=count_sku)

        create_history_prices = {}

        for i in range(num_chunks):
            list_sku = self._get_request_sku_competitors(
                path="/api/v1/price_history_competitors/get_sku/",
                range=i * self.chunk_size,
            )

            results = []

            for sku in list_sku:
                result = get_request_mpstats.delay(token_mp_stats, sku)
                results.append(result)

            for result in results:
                try:
                    sku, ad = result.get(timeout=None)
                except Exception as e:
                    raise Exception(f"Ошибка при импорте файла: {e}")
                
                if sku not in create_history_prices:
                    create_history_prices[sku] = []

                create_history_prices[sku].append(ad)

        with open("data.txt", "w") as file:
            file.write(str(create_history_prices))

        return "Success!"
    

class SendInOdoo(OdooAuth):
    def __init__(self) -> None:
        super().__init__()

    def main(self):
        with open("data.txt", "r") as file:
            data_content = file.read()

        data_dict = ast.literal_eval(data_content)
       
        path = "/api/v1/price_history_competitors/create_ads/"
        headers = self.connect_to_odoo_api_with_auth()

        results = []

        for sku, history_prices in data_dict.items():
            result = get_request_create_history_price.delay(
                endpoint=f"{self.url}{path}",
                headers=headers,
                data={"ads": str(history_prices), "sku": sku},
            )
            results.append(result)

        for result in results:
            try:
                result.get(timeout=None)
            except Exception as e:
                raise Exception(f"Ошибка при импорте файла: {e}")