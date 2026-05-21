# -*- coding: utf-8 -*-
from pages.partition import _db_page


def page_query():
    return _db_page('query', 'Query Check',
                    'Query base collection status per instance (ora_sql_plan / ora_bind_value / etc.)',
                    'query', inst_filter=True)
