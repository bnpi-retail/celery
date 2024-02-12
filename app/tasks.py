# import asyncio
# from dataclasses import dataclass
# from datetime import timedelta

# from temporalio import activity, workflow
# from temporalio.client import Client
# from temporalio.worker import Worker


# with workflow.unsafe.imports_passed_through():
#     from main import task_import__products


# @dataclass
# class ComposeGreetingInput:
#     greeting: str
#     name: str


# @activity.defn
# async def compose_greeting(input: ComposeGreetingInput) -> str:
#     results = []

#     for _ in range(3):
#         result = task_import__products.delay()
#         results.append(result)

#     for result in results:
#         try:
#             result.get(timeout=None)
#         except Exception as e:
#             raise Exception(f"Ошибка при импорте файла: {e}")

#     return f"{input.greeting}, {input.name}!"


# @workflow.defn
# class GreetingWorkflow:
#     @workflow.run
#     async def run(self, name: str) -> str:
#         workflow.logger.info("Running workflow with parameter %s" % name)
#         return await workflow.execute_activity(
#             compose_greeting,
#             ComposeGreetingInput("Hello", name),
#             start_to_close_timeout=timedelta(seconds=10),
#         )


# async def main():
#     client = await Client.connect("localhost:7233")

#     async with Worker(
#         client,
#         task_queue="hello-activity-task-queue",
#         workflows=[GreetingWorkflow],
#         activities=[compose_greeting],
#     ):

#         result = await client.execute_workflow(
#             GreetingWorkflow.run,
#             "World",
#             id="hello-activity-workflow-id",
#             task_queue="hello-activity-task-queue",
#         )
#         print(f"Result: {result}")


# if __name__ == "__main__":
#     asyncio.run(main())










import asyncio
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.common import RetryPolicy


# async def compose_greeting() -> str:
#     results = []

#     for _ in range(3):
#         result = task_import__products.delay()
#         results.append(result)

#     for result in results:
#         try:
#             result.get(timeout=None)
#         except Exception as e:
#             raise Exception(f"Ошибка при импорте файла: {e}")

#     return f"{input.greeting}, {input.name}!"


with workflow.unsafe.imports_passed_through():
    from price_histry_competitors_v2 import ParsingMPStats, SendInOdoo


@activity.defn
async def parsing_mp_stats_activity() -> None:
    ParsingMPStats().main()


@activity.defn
async def send_in_odoo_activity() -> None:
    SendInOdoo().main()


@workflow.defn
class CreatePriceHistoryMPStatsWorkflow:
    @workflow.run
    async def run(self) -> None:
        await workflow.execute_activity(
            parsing_mp_stats_activity,
            start_to_close_timeout=timedelta(seconds=20000),
            retry_policy=RetryPolicy(maximum_interval=timedelta(hours=24)),
        )

        await workflow.execute_activity(
            send_in_odoo_activity,
            start_to_close_timeout=timedelta(seconds=20000),
            retry_policy=RetryPolicy(maximum_interval=timedelta(hours=24)),
        )

@workflow.defn
class GeneralMPStatsWorkflow:
    @workflow.run
    async def run(self) -> None:

        workflow_id = "price-competitors-child-workflow-id"

        return await workflow.execute_child_workflow(
            CreatePriceHistoryMPStatsWorkflow.run,
            id=workflow_id,
        )

async def main():
    client = await Client.connect("localhost:7233")

    task_queue = "general-mp-stat-task-queue"
    workflow_id = "general-mp-stat-workflow-id"

    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[GeneralMPStatsWorkflow, CreatePriceHistoryMPStatsWorkflow],
        activities=[parsing_mp_stats_activity, send_in_odoo_activity],
    ):

        result = await client.execute_workflow(
            GeneralMPStatsWorkflow.run,
            id=workflow_id,
            task_queue=task_queue,
        )
        print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
