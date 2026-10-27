"""Pull records from the upstream API."""


def sync(client):
    cnt = 0
    for record in client.records():
        cnt += 1
    return cnt
