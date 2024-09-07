import pandas as pd
from app.config.config import Config
from app.util.DotDict import DotDict


def get_top_proxies(context, limit):
    # fetch data from DB
    isps = context.get_all_isps()
    isps = pd.DataFrame([(isp.id, isp.name) for isp in isps], columns=["id", "name"])

    agents = context.get_all_agents()
    agents = pd.DataFrame(
        [(agent.id, agent.isp_id, agent.name) for agent in agents],
        columns=["id", "isp_id", "name"],
    )

    proxies = context.get_connected_proxise()
    proxies = pd.DataFrame(
        [
            (proxy.id, proxy.server, proxy.port, proxy.secret, proxy.ip)
            for proxy in proxies
        ],
        columns=["id", "server", "port", "secret", "ip"],
    )
    ping_reports = context.get_connected_proxise_ping_reports()
    ping_reports = pd.DataFrame(
        [
            (
                report.id,
                report.agent_id,
                report.proxy_id,
                report.ping,
                report.updated_at,
            )
            for report in ping_reports
        ],
        columns=["id", "agent_id", "proxy_id", "ping", "updated_at"],
    )
    speed_reports = context.get_connected_proxise_speed_reports()
    speed_reports = pd.DataFrame(
        [
            (
                report.id,
                report.agent_id,
                report.proxy_id,
                report.speed,
                report.updated_at,
            )
            for report in speed_reports
        ],
        columns=["id", "agent_id", "proxy_id", "speed", "updated_at"],
    )
    # start process
    max_ping = Config.max_ping_value
    ping_reports["ping"] = ping_reports["ping"].replace(-1, max_ping)

    def average_ping(proxy_id):
        temp = ping_reports[ping_reports["proxy_id"] == proxy_id]
        temp = temp.sort_values(by="updated_at", ascending=False)
        if temp.shape[0] == 0:
            return max_ping
        temp = temp.iloc[: Config.contribute_history, :]
        temp = temp.reset_index(drop=True)
        decay_series = Config.exponential_decay**temp.index  # todo
        average_ping = (temp["ping"] * decay_series).sum()
        average_ping /= sum(decay_series)
        return average_ping

    proxies["average_ping"] = proxies["id"].apply(lambda id: average_ping(id))

    def average_speed(proxy_id):
        temp = speed_reports[speed_reports["proxy_id"] == proxy_id]
        temp = temp.sort_values(by="updated_at", ascending=False)
        if temp.shape[0] == 0:
            return 0
        temp = temp.iloc[: Config.contribute_history, :]
        temp = temp.reset_index(drop=True)
        decay_series = Config.exponential_decay**temp.index  # todo
        average_speed = (temp["speed"] * decay_series).sum()
        average_speed /= sum(decay_series)
        return average_speed

    proxies["average_speed"] = proxies["id"].apply(lambda id: average_speed(id))

    # scale and convert to score
    proxies["ping_score"] = (max_ping - proxies["average_ping"]) / max_ping

    max_speed = proxies["average_speed"].max()
    proxies["speed_score"] = proxies["average_speed"] / max_speed

    proxies["score"] = (
        proxies["ping_score"] * Config.ping_score_weight
        + proxies["speed_score"] * Config.speed_score_weight
    )

    proxies = proxies.sort_values(by="score", ascending=False)
    # select random from top 20
    rand_number = 20
    if len(proxies) < 20:
        rand_number = limit
    proxies = proxies.iloc[:rand_number, :]
    proxies = proxies.sample(n=min(proxies.shape[0], limit))
    proxies = proxies.sort_values(by="score", ascending=False)

    results = []
    for index, row in proxies.iterrows():
        results.append(
            DotDict(
                {
                    "server": row["server"],
                    "port": row["port"],
                    "secret": row["secret"],
                    "average_speed": row["average_speed"],
                    "average_ping": row["average_ping"],
                }
            )
        )

    return results
