import os
import mysql.connector
from sqlalchemy import create_engine, text, func, or_
from sqlalchemy.orm import sessionmaker
from app.util.DotDict import DotDict

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


class Context:
    def __init__(self):
        # config
        self.max_report_ping = 30
        self.max_report_speed = 10
        self.max_timeouts = 5
        self.successful_pings = 5
        #
        db_name = os.getenv("database_name")
        db_user = os.getenv("database_user")
        db_pass = os.getenv("database_pass")
        db_host = os.getenv("database_host")
        db_port = os.getenv("database_port")
        db_url = f"mysql+mysqlconnector://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
        self.engine = create_engine(db_url, isolation_level="AUTOCOMMIT")
        Base.metadata.create_all(self.engine)

    def _session(self):
        Session = sessionmaker(bind=self.engine,)
        return Session()

    def _exec(self, query, session=None):
        new_session = None
        try:
            if session:
                if not session.is_active:
                    session.begin()
                result = query(session)
                return result
            else:
                new_session = self._session()
                if not new_session.is_active:
                    with new_session.begin() as transaction:
                        result = query(new_session)
                else:
                    result = query(new_session)

                if new_session.dirty:
                    new_session.commit()
                new_session.close()
                return result

        except Exception as e:
            print(f"An error occurred: {str(e)}")
            if new_session:
                new_session.rollback()
                new_session.close()
            raise e

    # channel
    def get_all_channel(self, session=None):
        return self._exec(
            lambda sess: sess.query(Channel)
            .filter(Channel.deleted_at == None)
            .all(), session)

    def count_channels(self, session=None):
        return self._exec(
            lambda sess: sess.query(func.count(Channel.id))
            .filter(Channel.deleted_at == None)
            .scalar(), session)

    def add_proxies_of_channel(self, proxies, channel, last_message_id, session=None):
        def _f(session):
            for proxy in proxies:
                self.add_proxy(proxy.server, proxy.port, proxy.secret, session)
            session.add(channel)
            channel.last_id = last_message_id
        return self._exec(_f, session)

    # proxy
    def count_connect_proxies(self, session=None):
        return self._exec(
            lambda sess: sess.query(func.count(Proxy.id)).filter(
                Proxy.connect == 1,
                Proxy.deleted_at == None
            ).scalar(), session)

    def count_total_proxies(self, session=None):
        # include deleted_at
        return self._exec(
            lambda sess: sess.query(func.count(Proxy.id))
            .scalar(), session)

    def get_connected_proxise(self, session=None):
        return self._exec(
            lambda sess: sess.query(Proxy).filter(
                Proxy.connect == 1,
                Proxy.deleted_at == None
            ).all(), session)

    def get_proxy(self, server, port, secret, session=None):
        # include deleted_at
        return self._exec(
            lambda sess: sess.query(Proxy).filter(
                Proxy.server == server,
                Proxy.port == port,
                Proxy.secret == secret).first(), session)

    def add_proxy(self, server, port, secret, session=None):
        def _f(session):
            proxy = self.get_proxy(server, port, secret, session)
            if (not proxy):
                new_proxy = Proxy(server=server, port=port, secret=secret)
                session.add(new_proxy)
            elif (proxy.deleted_at):
                proxy.deleted_at = None
        return self._exec(_f, session)

    def get_proxy_ping(self, agent_id, disconnect, session=None):
        if (disconnect):
            return self._exec(
                lambda sess: sess.query(Proxy).filter(
                    Proxy.connect == 0,
                    Proxy.deleted_at == None
                ).all(), session)
        else:
            return self._exec(
                lambda sess: sess.query(Proxy).filter(
                    or_(Proxy.connect.is_(None), Proxy.connect == 1),
                    Proxy.deleted_at == None
                ).all(), session)

    def get_proxy_speed(self, agent_id, session=None):
        return self._exec(
            lambda sess: sess.query(Proxy).filter(
                Proxy.connect == 1,
                Proxy.deleted_at == None
            ).all(), session)

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
	                END;
                """
            session.execute(text(query))
        return self._exec(_f, session)

    def delete_dead_proxies(self, threshold, session=None):
        def _f(session):
            query = f"""
                    UPDATE proxy set deleted_at = NOW()
                        WHERE deleted_at is null and proxy.id in (
    	                    SELECT proxy_id FROM `ping_report`
	                            WHERE ping = -1 and deleted_at is null
	                            GROUP by proxy_id
	                            HAVING COUNT(id) >= {threshold}
	                );
                    """
            session.execute(text(query))
            query = f"""
                    DELETE FROM ping_report
                        WHERE
                            ping_report.proxy_id in (
                                SELECT proxy.id FROM proxy
                                    WHERE deleted_at is not null
                            );
                    """
            session.execute(text(query))
            query = f"""
                    DELETE FROM speed_report
                        WHERE
                            speed_report.proxy_id in (
                                SELECT proxy.id FROM proxy
                                    WHERE deleted_at is not null
                    );
                """
            session.execute(text(query))
        return self._exec(_f, session)

    def get_all_isps(self, session=None):
        return self._exec(
            lambda sess: sess.query(ISP)
            .filter(ISP.deleted_at == None)
            .all(), session)
    # agent

    def get_agent(self, agent_id, session=None):
        return self._exec(lambda sess: sess.query(Agent)
                          .filter(
                              Agent.id == agent_id,
                              Agent.deleted_at == None)
                          .first(), session)

    def get_all_agents(self, session=None):
        return self._exec(
            lambda sess: sess.query(Agent)
            .filter(Agent.deleted_at == None)
            .all(), session)

    # ping report
    def get_connected_proxise_ping_reports(self, session=None):
        return self._exec(
            lambda sess: sess.query(PingReport).filter(
                PingReport.proxy_id.in_(
                    sess.query(Proxy.id)
                    .filter(
                        Proxy.connect == 1,
                        Proxy.deleted_at == None
                    )
                )
            ).all(), session)

    def get_ping_report_count(self, proxy_id, session=None):
        return self._exec(
            lambda sess: sess.query(func.count(PingReport.id)).filter_by(
                proxy_id=proxy_id
            ).scalar(), session)

    def add_ping_report(self, agent_id, proxy_id, ping, session=None):
        def _f(session):
            new_report = PingReport(
                agent_id=agent_id,
                proxy_id=proxy_id,
                ping=ping
            )
            session.add(new_report)
            count = self.get_ping_report_count(proxy_id, session)
            if (count >= self.max_report_ping):
                for _ in range(self.max_report_ping, count):
                    oldest_report = session.query(PingReport).filter_by(
                        proxy_id=proxy_id
                    ).order_by(PingReport.updated_at).first()
                    session.delete(oldest_report)

        return self._exec(_f, session)

    def add_bach_ping_report(self, agent_id, reports, session=None):
        def _f(session):
            for report in reports:
                report = DotDict(report)
                self.add_ping_report(
                    agent_id,
                    report.proxy_id,
                    report.ping,
                    session
                )
        return self._exec(_f, session)

    # speed report
    def get_connected_proxise_speed_reports(self, session=None):
        return self._exec(
            lambda sess: sess.query(SpeedReport).filter(
                SpeedReport.proxy_id.in_(
                    sess.query(Proxy.id)
                    .filter(
                        Proxy.connect == 1,
                        Proxy.deleted_at == None
                    )
                )
            ).all(), session)

    def get_speed_report_count(self, proxy_id, session=None):
        return self._exec(
            lambda sess: sess.query(func.count(SpeedReport.id)).filter_by(
                proxy_id=proxy_id
            ).scalar(), session)

    def add_speed_report(self, agent_id, proxy_id, speed, session=None):
        def _f(session):
            new_report = SpeedReport(
                agent_id=agent_id, proxy_id=proxy_id, speed=speed)
            session.add(new_report)
            count = self.get_speed_report_count(proxy_id, session)
            if (count >= self.max_report_speed):
                for _ in range(self.max_report_speed, count):
                    oldest_report = session.query(SpeedReport).filter_by(
                        proxy_id=proxy_id
                    ).order_by(SpeedReport.updated_at).first()
                    session.delete(oldest_report)
        return self._exec(_f, session)

    def add_bach_speed_report(self, agent_id, reports, session=None):
        def _f(session):
            for report in reports:
                report = DotDict(report)
                self.add_speed_report(
                    agent_id,
                    report.proxy_id,
                    report.speed,
                    session
                )
        return self._exec(_f, session)

    # setting
    def get_setting(self, key, session=None):
        return self._exec(
            lambda sess: sess.query(Setting).filter_by(key=key).first(), session)

    def add_or_update_setting(self, key, value, session=None):
        def _f(session):
            setting = self.get_setting(key, session)
            if setting:
                setting.value = value
            else:
                new_setting = Setting(key=key, value=value)
                self.session.add(new_setting)
        return self._exec(_f, session)
