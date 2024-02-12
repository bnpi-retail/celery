import requests

from celery import Celery
from time import sleep

app = Celery('tasks')

app.conf.broker_url = "redis://localhost:6379/0"
app.conf.result_backend = "redis://localhost:6379/0"
app.conf.worker_concurrency = 4

@app.task
def task_import__products() -> bool:
    sleep(1)
    return True

@app.task
def get_request_mpstats(token_mpstats: str, sku: int):
    url = f"https://mpstats.io/api/oz/get/item/{sku}/sales"

    headers = {
        "X-Mpstats-TOKEN": token_mpstats,
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise ValueError(f"MP status: {response.status_code}")
    r_json = response.json()
    ad = r_json[-1]
    return sku, ad

@app.task
def get_request_create_history_price(endpoint: str, headers: str, data: dict):
    response = requests.post(endpoint, headers=headers, data=data)
    if response.status_code != 200:
        raise Exception(f"Данные товара не были отправлены!")
