# -*- coding: utf-8 -*-
from pages.partition import _db_page


def page_session():
    return _db_page('session', 'Session Check',
                    'Last session collection time per instance', 'session', inst_filter=True)
