import os
import time
import threading
import mysql.connector
from datetime import datetime
from sqlalchemy import create_engine, text, func, or_
from sqlalchemy.orm import sessionmaker
from app.util.DotDict import DotDict
from app.config.config import Config
from app.util.GeoIP import get_country
from datetime import datetime, timedelta, timezone

# models
from app.model.base import Base
from app.model.agent import Agent
from app.model.channel import Channel
from app.model.isp import ISP
from app.model.proxy import Proxy
from app.model.speed_report import SpeedReport
from app.model.ping_report import PingReport
from app.model.setting import Setting
from collections.abc import Iterable

# One engine (and therefore one connection pool) per process. Every Context()
# used to build its own engine, so the middleware and each controller held a
# separate pool and a single request borrowed connections from two of them.
_engine = None
_session_factory = None
_engine_lock = threading.Lock()


def _get_engine():
    global _engine, _session_factory
    if _engine is not None:
        return _engine
    with _engine_lock:
        if _engine is None:
            db_url = (
                f"mysql+mysqlconnector://{Config.database_user}:{Config.database_pass}"
                f"@{Config.database_host}:{Config.database_port}/{Config.database_name}"
            )
            engine = create_engine(
                db_url,
                isolation_level="AUTOCOMMIT",
                pool_size=Config.db_pool_size,
                max_overflow=Config.db_max_overflow,
                pool_timeout=Config.db_pool_timeout,
                pool_recycle=Config.db_pool_recycle,
                pool_pre_ping=True,
            )
            Base.metadata.create_all(engine)
            # Callers use the returned rows after _exec has closed the
            # session (middleware reads agent.encrypted_key, controllers call
            # to_json()), so loaded values must survive the commit.
            _session_factory = sessionmaker(bind=engine, expire_on_commit=False)
            _engine = engine
    return _engine


class Context:
    def __init__(self):
        # config
        self.max_report_ping = Config.max_report_ping
        self.max_report_speed = Config.max_report_speed
        self.max_timeouts = Config.max_timeouts
        self.successful_pings = Config.successful_pings
        #
        self.engine = _get_engine()

    def _session(self):
        _get_engine()
        return _session_factory()

    def _exec(self, query, session=None):
        # A caller-supplied session is owned by that caller: it opened the
        # transaction and it is responsible for commit/rollback/close.
        if session is not None:
            return query(session)

        last_error = None
        for attempt in range(1, Config.session_retry_max + 1):
            new_session = self._session()
            try:
                result = query(new_session)
                if new_session.in_transaction():
                    new_session.commit()
                return result
            except Exception as e:
                new_session.rollback()
                if "lock wait timeout" not in str(e).lower():
                    print(f"An error occurred: {str(e)}")
                    raise
                last_error = e
                print(f"Retrying... Attempt {attempt}")
            finally:
                # Runs on every path, including the raise above. Without this
                # the session (and its pooled connection) was leaked on error.
                new_session.close()
            time.sleep(Config.session_retry_interval)

        print(f"An error occurred: {str(last_error)}")
        raise last_error

    # channel
    def get_all_channel(self, limit=None, session=None):
        def query_func(sess):
            channels = (
                sess.query(Channel)
                .filter(Channel.deleted_at == None)
                .order_by(Channel.updated_at.asc())
                .all()
            )

            if limit is not None:
                channels = channels[:limit]
            return channels

        return self._exec(query_func, session)

    def count_channels(self, session=None):
        return self._exec(
            lambda sess: sess.query(func.count(Channel.id))
            .filter(Channel.deleted_at == None)
            .scalar(),
            session,
        )

    def add_proxies_of_channel(self, proxies, channel, last_message_id, session=None):
        def _f(session):
            for proxy in proxies:
                self.add_proxy(proxy.server, proxy.port, proxy.secret, session)
            channel.last_id = last_message_id
            channel.updated_at = datetime.now()
            session.add(channel)

        return self._exec(_f, session)

    # proxy
    def count_connect_proxies(self, session=None):
        return self._exec(
            lambda sess: sess.query(func.count(Proxy.id))
            .filter(Proxy.connect == 1, Proxy.deleted_at == None)
            .scalar(),
            session,
        )

    def count_total_proxies(self, session=None):
        # include deleted_at
        return self._exec(
            lambda sess: sess.query(func.count(Proxy.id)).scalar(), session
        )

    def get_connected_proxise(self, country=None, session=None):
        def _f(sess):
            q = sess.query(Proxy).filter(Proxy.connect == 1, Proxy.deleted_at == None)
            if country:
                q = q.filter(Proxy.country == country)
            results = q.all()
            if not results and Config.fallback_null_connect:
                q = sess.query(Proxy).filter(Proxy.connect.is_(None), Proxy.deleted_at == None)
                if country:
                    q = q.filter(Proxy.country == country)
                results = q.all()
            return results

        return self._exec(_f, session)

    def get_proxy(self, server, port, secret, session=None):
        # include deleted_at
        return self._exec(
            lambda sess: sess.query(Proxy)
            .filter(Proxy.server == server, Proxy.port == port, Proxy.secret == secret)
            .first(),
            session,
        )

    def add_proxy(self, server, port, secret, session=None):
        def _f(session):
            proxy = self.get_proxy(server, port, secret, session)
            if not proxy:
                country = get_country(server)
                new_proxy = Proxy(
                    server=server, port=port, secret=secret, country=country
                )
                session.add(new_proxy)
            elif proxy.deleted_at:
                # local time, to match func.now() defaults and the deleted_at
                # values written by soft_delete_proxy
                wait_time = datetime.now() - timedelta(days=3)
                if proxy.deleted_at < wait_time:
                    proxy.deleted_at = None

        return self._exec(_f, session)

    def get_proxy_ping(self, agent_id, disconnect, country=None, session=None):
        def _f(sess):
            if disconnect:
                q = sess.query(Proxy).filter(
                    Proxy.connect == 0, Proxy.deleted_at == None
                )
            else:
                q = sess.query(Proxy).filter(
                    or_(Proxy.connect.is_(None), Proxy.connect == 1),
                    Proxy.deleted_at == None,
                )
            if country:
                q = q.filter(Proxy.country == country)
            return q.order_by(func.random()).limit(5000).all()

        return self._exec(_f, session)

    def get_proxy_speed(self, agent_id, country=None, session=None):
        def _f(sess):
            q = sess.query(Proxy).filter(Proxy.connect == 1, Proxy.deleted_at == None)
            if country:
                q = q.filter(Proxy.country == country)
            return q.order_by(func.random()).limit(50).all()

        return self._exec(_f, session)

    def proxies_connection_update(self, session=None):
        def _f(session):
            query = f"""
                    UPDATE proxy
	                JOIN (
	                	SELECT proxy_id, sum(timeouts) as timeouts, sum(successful_pings) as successful_pings
	                		from (
                                SELECT
                                	report.proxy_id as proxy_id,
	                				CASE WHEN report.ping = -1 THEN 1 ELSE 0 END AS timeouts,
                                    CASE WHEN report.ping != -1 THEN 1 ELSE 0 END AS successful_pings
                                FROM ping_report as report
	                			) p GROUP BY p.proxy_id
                     ) AS subquery ON proxy.id = subquery.proxy_id
	                SET proxy.connect = CASE
	                	WHEN subquery.timeouts >= {self.max_timeouts} THEN 0
	                	WHEN subquery.successful_pings >= {self.successful_pings} THEN 1
	                	ELSE NULL
	                END
                    WHERE proxy.deleted_at IS NULL;
                """
            session.execute(text(query))

        return self._exec(_f, session)

    def soft_delete_proxy(self, proxy_id, session=None):
        def _f(session):
            proxy = session.query(Proxy).filter(Proxy.id == proxy_id).one_or_none()
            if proxy:
                proxy.deleted_at = datetime.now()
                session.add(proxy)
                session.query(PingReport).filter(
                    PingReport.proxy_id == proxy_id
                ).delete()
                session.query(SpeedReport).filter(
                    SpeedReport.proxy_id == proxy_id
                ).delete()
            else:
                print(f"Proxy with id {proxy_id} not found.")

        return self._exec(_f, session)

    def soft_delete_proxies(self, proxy_ids, session=None):
        """Soft-delete many proxies with a handful of bulk statements.

        The per-id path costs one request, one session and four statements per
        proxy; a ping round produces thousands of them at once.
        """
        ids = sorted({int(i) for i in proxy_ids or []})
        if not ids:
            return 0

        def _f(sess):
            now = datetime.now()
            affected = 0
            for start in range(0, len(ids), Config.soft_delete_chunk_size):
                chunk = ids[start : start + Config.soft_delete_chunk_size]
                sess.query(PingReport).filter(PingReport.proxy_id.in_(chunk)).delete(
                    synchronize_session=False
                )
                sess.query(SpeedReport).filter(SpeedReport.proxy_id.in_(chunk)).delete(
                    synchronize_session=False
                )
                affected += (
                    sess.query(Proxy)
                    .filter(Proxy.id.in_(chunk), Proxy.deleted_at.is_(None))
                    .update({Proxy.deleted_at: now}, synchronize_session=False)
                )
            return affected

        return self._exec(_f, session)

    def hard_delete_proxy(self, proxy_id, session=None):
        def _f(session):
            proxy = session.query(Proxy).filter(Proxy.id == proxy_id).one_or_none()
            if proxy:
                session.delete(proxy)
            else:
                print(f"Proxy with id {proxy_id} not found.")

        return self._exec(_f, session)

    def delete_dead_proxies(self, threshold, ping_limit, session=None):
        # Get the list of proxy IDs to be deleted
        def get_dead_proxies(session):
            subquery_ping_report = (
                session.query(PingReport.proxy_id)
                .filter(
                    PingReport.deleted_at.is_(None),
                    or_(PingReport.ping == -1, PingReport.ping > ping_limit),
                )
                .group_by(PingReport.proxy_id)
                .having(func.count(PingReport.id) >= threshold)
            )
            return subquery_ping_report.all()

        dead_proxies = self._exec(get_dead_proxies, session)

        # One session and four statements per proxy used to be opened here;
        # soft_delete_proxies does the same work in bulk.
        return self.soft_delete_proxies(
            [proxy_id for (proxy_id,) in dead_proxies], session
        )

    def get_all_isps(self, session=None):
        return self._exec(
            lambda sess: sess.query(ISP).filter(ISP.deleted_at == None).all(), session
        )

    # agent

    def get_agent(self, agent_id, session=None):
        return self._exec(
            lambda sess: sess.query(Agent)
            .filter(Agent.id == agent_id, Agent.deleted_at == None)
            .first(),
            session,
        )

    def get_all_agents(self, session=None):
        return self._exec(
            lambda sess: sess.query(Agent).filter(Agent.deleted_at == None).all(),
            session,
        )

    # ping report
    def cleanup_old_ping_reports(self, session=None):
        """Keep only the newest max_report_ping reports per proxy.

        This used to run a count, a select and a row-by-row delete for every
        proxy in one transaction -- thousands of round trips holding a single
        connection and its locks. One window-function delete does the same job.
        """

        def _f(session):
            query = """
                DELETE report FROM ping_report AS report
                JOIN (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY proxy_id ORDER BY updated_at DESC, id DESC
                    ) AS rn
                    FROM ping_report
                ) AS ranked ON ranked.id = report.id
                WHERE ranked.rn > :max_reports
            """
            result = session.execute(
                text(query), {"max_reports": self.max_report_ping}
            )
            return result.rowcount

        return self._exec(_f, session)

    def get_connected_proxise_ping_reports(self, session=None):
        return self._exec(
            lambda sess: sess.query(PingReport)
            .filter(
                PingReport.proxy_id.in_(
                    sess.query(Proxy.id).filter(
                        Proxy.connect == 1, Proxy.deleted_at == None
                    )
                )
            )
            .all(),
            session,
        )

    def get_ping_report_count(self, proxy_id, session=None):
        return self._exec(
            lambda sess: sess.query(func.count(PingReport.id))
            .filter_by(proxy_id=proxy_id)
            .scalar(),
            session,
        )

    def add_ping_report(self, agent_id, proxy_id, ping, session=None):
        def _f(session):
            new_report = PingReport(agent_id=agent_id, proxy_id=proxy_id, ping=ping)
            session.add(new_report)
            # count = self.get_ping_report_count(proxy_id, session)
            # if (count >= self.max_report_ping):
            #     for _ in range(self.max_report_ping, count):
            #         oldest_report = session.query(PingReport).filter_by(
            #             proxy_id=proxy_id
            #         ).order_by(PingReport.updated_at).first()
            #         session.delete(oldest_report)

        return self._exec(_f, session)

    def add_bach_ping_report(self, agent_id, reports, session=None):
        def _f(session):
            for report in reports:
                report = DotDict(report)
                self.add_ping_report(agent_id, report.proxy_id, report.ping, session)

        return self._exec(_f, session)

    # speed report
    def get_connected_proxise_speed_reports(self, session=None):
        return self._exec(
            lambda sess: sess.query(SpeedReport)
            .filter(
                SpeedReport.proxy_id.in_(
                    sess.query(Proxy.id).filter(
                        Proxy.connect == 1, Proxy.deleted_at == None
                    )
                )
            )
            .all(),
            session,
        )

    def get_speed_report_count(self, proxy_id, session=None):
        return self._exec(
            lambda sess: sess.query(func.count(SpeedReport.id))
            .filter_by(proxy_id=proxy_id)
            .scalar(),
            session,
        )

    def add_speed_report(self, agent_id, proxy_id, speed, session=None):
        def _f(session):
            new_report = SpeedReport(agent_id=agent_id, proxy_id=proxy_id, speed=speed)
            session.add(new_report)
            count = self.get_speed_report_count(proxy_id, session)
            if count >= self.max_report_speed:
                for _ in range(self.max_report_speed, count):
                    oldest_report = (
                        session.query(SpeedReport)
                        .filter_by(proxy_id=proxy_id)
                        .order_by(SpeedReport.updated_at)
                        .first()
                    )
                    session.delete(oldest_report)

        return self._exec(_f, session)

    def add_bach_speed_report(self, agent_id, reports, session=None):
        def _f(session):
            for report in reports:
                report = DotDict(report)
                self.add_speed_report(agent_id, report.proxy_id, report.speed, session)

        return self._exec(_f, session)

    # setting
    def get_setting(self, key, session=None):
        return self._exec(
            lambda sess: sess.query(Setting).filter_by(key=key).first(), session
        )

    def add_or_update_setting(self, key, value, session=None):
        def _f(session):
            setting = self.get_setting(key, session)
            if setting:
                setting.value = value
            else:
                new_setting = Setting(key=key, value=value)
                session.add(new_setting)

        return self._exec(_f, session)
