import os
import socket
import geoip2.database

_db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'GeoLite2-Country.mmdb')
_reader = geoip2.database.Reader(os.path.abspath(_db_path))


def get_country(server):
    try:
        ip = socket.gethostbyname(server)
        response = _reader.country(ip)
        return response.country.iso_code
    except Exception:
        return None
