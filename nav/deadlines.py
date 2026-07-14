from __future__ import annotations

import datetime


def kovetkezo_afa_hatarido() -> tuple[datetime.date, int]:
    ma = datetime.date.today()
    kov_honap = ma.replace(day=28) + datetime.timedelta(days=4)
    esedekesseg = datetime.date(kov_honap.year, kov_honap.month, 20)
    hatra_van = (esedekesseg - ma).days
    return esedekesseg, hatra_van