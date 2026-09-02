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
            (proxy.id, proxy.server, proxy.port, proxy.secret)
            for proxy in proxies
        ],
        columns=["id", "server", "port", "secret"],
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
    ping_reports["ping"] = ping_reports["ping"].replace(-1, max_ping)

    # One groupby instead of copying and rescanning the whole frame per proxy.
    ping_stats = (
        ping_reports.groupby("proxy_id")["ping"].agg(["mean", "min", "max"])
        if not ping_reports.empty
        else None
    )

    def _ping_stat(stat):
        if ping_stats is None:
            return proxies["id"].map(lambda _: "-")
        return proxies["id"].map(ping_stats[stat]).fillna("-")

    proxies[titles.ping_avg] = _ping_stat("mean").map(
        lambda v: round(v) if v != "-" else v
    )
    proxies[titles.ping_min] = _ping_stat("min")
    proxies[titles.ping_max] = _ping_stat("max")

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

    # speed == 0 means the download timed out, not a real measurement
    measured_speed = speed_reports[speed_reports["speed"] != 0]
    speed_stats = (
        measured_speed.groupby("proxy_id")["speed"].agg(["mean", "min", "max"])
        if not measured_speed.empty
        else None
    )

    def _speed_stat(stat):
        if speed_stats is None:
            return proxies["id"].map(lambda _: "-")
        return proxies["id"].map(speed_stats[stat]).fillna("-")

    proxies[titles.speed_avg] = _speed_stat("mean").map(
        lambda v: round(v) if v != "-" else v
    )
    proxies[titles.speed_min] = _speed_stat("min")
    proxies[titles.speed_max] = _speed_stat("max")

    def score(row):
        # Sorted descending, so higher must mean better. Speed already is;
        # ping is not, so it has to be inverted -- returning ping/1000 put the
        # slowest proxies at the top of the file.
        if row[titles.speed_max] != "-":
            return row[titles.speed_max]
        if row[titles.ping_avg] != "-":
            return (max_ping - row[titles.ping_avg]) / max_ping
        return 0

    proxies["score"] = proxies.apply(lambda row: score(row), axis=1)
    proxies = proxies.sort_values(by="score", ascending=False)
    del proxies["id"], proxies["score"]

    def create_url(row):
        return f"https://t.me/proxy?server={row['server']}&port={row['port']}&secret={row['secret']}"

    proxies["url"] = proxies.apply(lambda row: create_url(row), axis=1)
    proxies = proxies[["url"] + proxies.columns[:-1].tolist()]

    proxies.to_csv(path, index=None)
