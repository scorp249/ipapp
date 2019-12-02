import asyncio
from typing import Any, Awaitable, Callable, Optional

import asyncpg
import pika
import pytest
from async_timeout import timeout as async_timeout

TIMEOUT = 1
COMPOSE_POSTGRES_URL = 'postgres://ipapp:secretpwd@127.0.0.1:58971/ipapp'
COMPOSE_RABBITMQ_URL = 'amqp://guest:guest@127.0.0.1:58972/'


def pytest_addoption(parser):
    parser.addoption(
        "--postgres-url",
        dest="postgres_url",
        help="Postgres override connection string",
        metavar="postgres://user:pwd@host:port/dbname",
    )
    parser.addoption(
        "--rabbit-url",
        dest="rabbit_url",
        help="RabbitMq override connection string",
        metavar="amqp://user:pwd@host:port/vhost",
    )


async def wait_service(
    url: str,
    timeout: float,
    check_fn: Callable[[str], Awaitable[Any]],
    err_template: str,
) -> None:
    last_err: Optional[Exception] = None
    try:
        with async_timeout(timeout):
            while True:
                try:
                    await check_fn(url)
                    break
                except Exception as err:
                    last_err = err
                    print(type(err))
                    import traceback

                    print(traceback.format_exc())
                    await asyncio.sleep(0.1)
    except asyncio.TimeoutError:
        raise TimeoutError(err_template.format(url=url, err=last_err))


@pytest.fixture
async def postgres_url(request) -> str:
    url = request.config.getoption('postgres_url')
    if not url:
        url = COMPOSE_POSTGRES_URL
    await wait_service(
        url,
        TIMEOUT,
        asyncpg.connect,
        'Failed to connect to {url}. Last error: {err}',
    )
    yield url


@pytest.fixture
async def rabbitmq_url(request) -> str:
    async def check(url):
        await asyncio.get_event_loop().run_in_executor(
            None, pika.BlockingConnection, pika.URLParameters(url)
        )

    url = request.config.getoption('rabbit_url')
    if not url:
        url = COMPOSE_RABBITMQ_URL
    await wait_service(
        url, TIMEOUT, check, 'Failed to connect to {url}. Last error: {err}',
    )
    yield url