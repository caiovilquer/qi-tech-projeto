from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import constants

ZONE = ZoneInfo('America/Sao_Paulo')


def pix_window(timestamp):
    local=timestamp.astimezone(ZONE)
    day=local.date()
    if 6<=local.hour<20:
        start=datetime.combine(day,time(6),ZONE)
        end=datetime.combine(day,time(20),ZONE)
        limit=constants.PIX_DAY_LIMIT
    else:
        if local.hour<6: day-=timedelta(days=1)
        start=datetime.combine(day,time(20),ZONE)
        end=datetime.combine(day+timedelta(days=1),time(6),ZONE)
        limit=constants.PIX_NIGHT_LIMIT
    return start.astimezone(timezone.utc),end.astimezone(timezone.utc),limit
