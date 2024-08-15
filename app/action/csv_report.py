import pandas as pd
from app.config.config import Config
from app.util.DotDict import DotDict


titles = DotDict(
    {
        "ping_avg": "average ping time(ms)",
        "ping_min": "min ping time(ms)",
        "ping_max": "max ping time(ms)",
        "speed_avg": "average download speed(KB)",
        "speed_min": "min download speed(KB)",
        "speed_max": "max download speed(KB)",
    }
)


def create_csv_report(context, path, limit):
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

    max_ping = Config.max_ping_value

    def ping_average(proxy_id):
        ping_df = ping_reports.copy()
        ping_df["ping"] = ping_df["ping"].replace(-1, max_ping)
        temp = ping_df[ping_df["proxy_id"] == proxy_id]
        if temp.shape[0] == 0:
            return "-"
        return round(temp["ping"].mean())

    proxies[titles.ping_avg] = proxies["id"].apply(lambda id: ping_average(id))

    def ping_min(proxy_id):
        ping_df = ping_reports.copy()
        ping_df["ping"] = ping_df["ping"].replace(-1, max_ping)
        temp = ping_df[ping_df["proxy_id"] == proxy_id]
        if temp.shape[0] == 0:
            return "-"
        return temp["ping"].min()

    proxies[titles.ping_min] = proxies["id"].apply(lambda id: ping_min(id))

    def ping_max(proxy_id):
        ping_df = ping_reports.copy()
        temp = ping_df[ping_df["proxy_id"] == proxy_id]
        if temp.shape[0] == 0:
            return "-"
        return temp["ping"].max()

    proxies[titles.ping_max] = proxies["id"].apply(lambda id: ping_max(id))

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

    def speed_average(proxy_id):
        temp = speed_reports[speed_reports["proxy_id"] == proxy_id]
        temp = temp[temp["speed"] != 0]
        if temp.shape[0] == 0:
            return "-"
        return round(temp["speed"].mean())

    proxies[titles.speed_avg] = proxies["id"].apply(lambda id: speed_average(id))

    def speed_min(proxy_id):
        temp = speed_reports[speed_reports["proxy_id"] == proxy_id]
        temp = temp[temp["speed"] != 0]
        if temp.shape[0] == 0:
            return "-"
        return temp["speed"].min()

    proxies[titles.speed_min] = proxies["id"].apply(lambda id: speed_min(id))

    def speed_max(proxy_id):
        temp = speed_reports[speed_reports["proxy_id"] == proxy_id]
        temp = temp[temp["speed"] != 0]
        if temp.shape[0] == 0:
            return "-"
        return temp["speed"].max()

    proxies[titles.speed_max] = proxies["id"].apply(lambda id: speed_max(id))

    def score(row):
        if row[titles.speed_max] != "-":
            return row[titles.speed_max]
        if row[titles.ping_max] != "-":
            return row[titles.ping_max] / 1000
        return 0

    proxies["score"] = proxies.apply(lambda row: score(row), axis=1)
    proxies = proxies.sort_values(by="score", ascending=False)
    del proxies["id"], proxies["ip"], proxies["score"]

    def create_url(row):
        return f"https://t.me/proxy?server={row['server']}&port={row['port']}&secret={row['secret']}"

    proxies["url"] = proxies.apply(lambda row: create_url(row), axis=1)
    proxies = proxies[["url"] + proxies.columns[:-1].tolist()]

    proxies.to_csv(path, index=None)
