import pandas as pd
from app.config.config import Config
from app.util.DotDict import DotDict


def _decayed_average(reports, value_column):
    """proxy_id -> exponentially decayed average of its newest reports.

    Same weighting as before (newest report weight 1, then decay**n, normalised
    by the sum of the weights) but computed in one pass instead of scanning the
    whole report table once per proxy.
    """
    if reports.empty:
        return {}
    df = reports.sort_values(
        by=["proxy_id", "updated_at"], ascending=[True, False]
    )
    df = df.groupby("proxy_id", sort=False).head(Config.contribute_history).copy()
    df["weight"] = Config.exponential_decay ** df.groupby(
        "proxy_id", sort=False
    ).cumcount()
    df["weighted"] = df[value_column] * df["weight"]
    totals = df.groupby("proxy_id", sort=False).agg(
        weighted=("weighted", "sum"), weight=("weight", "sum")
    )
    return (totals["weighted"] / totals["weight"]).to_dict()


def get_top_proxies(context, limit, country=None):
    # fetch data from DB
    isps = context.get_all_isps()
    isps = pd.DataFrame([(isp.id, isp.name) for isp in isps], columns=["id", "name"])

    agents = context.get_all_agents()
    agents = pd.DataFrame(
        [(agent.id, agent.isp_id, agent.name) for agent in agents],
        columns=["id", "isp_id", "name"],
    )

    proxies = context.get_connected_proxise(country=country)
    proxies = pd.DataFrame(
        [
            (proxy.id, proxy.server, proxy.port, proxy.secret, proxy.country)
            for proxy in proxies
        ],
        columns=["id", "server", "port", "secret", "country"],
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

    proxies["average_ping"] = (
        proxies["id"].map(_decayed_average(ping_reports, "ping")).fillna(max_ping)
    )
    proxies["average_speed"] = (
        proxies["id"].map(_decayed_average(speed_reports, "speed")).fillna(0.0)
    )

    # scale and convert to score
    proxies["ping_score"] = (max_ping - proxies["average_ping"]) / max_ping

    # With no speed reports at all max_speed is 0, and dividing by it turned
    # every score into NaN -- which silently destroyed the whole ranking.
    max_speed = proxies["average_speed"].max()
    if pd.isna(max_speed) or max_speed <= 0:
        proxies["speed_score"] = 0.0
    else:
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
                    "country": row["country"],
                    "average_speed": row["average_speed"],
                    "average_ping": row["average_ping"],
                }
            )
        )

    return results
