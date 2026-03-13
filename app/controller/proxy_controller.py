from app.Context import Context


class ProxyController:
    def __init__(self):
        self.context = Context()

    def get_proxies_ping(self, agent_id, disconnect, country=None):
        proxies = self.context.get_proxy_ping(agent_id, disconnect, country)
        result = []
        for proxy in proxies:
            result.append(proxy.to_json())
        return {"result": result}

    def get_proxies_speed(self, agent_id, country=None):
        proxies = self.context.get_proxy_speed(agent_id, country)
        result = []
        for proxy in proxies:
            result.append(proxy.to_json())
        return {"result": result}

    def delete_proxy(self, agent_id, proxy_id):
        self.context.hard_delete_proxy(proxy_id)

    def soft_delete_proxy(self, agent_id, proxy_id):
        self.context.soft_delete_proxy(proxy_id)
