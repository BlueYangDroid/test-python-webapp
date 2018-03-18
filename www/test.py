#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据访问测试代码"""

import orm
from models import User, Blog, Comment
import asyncio
import sys
import logging; logging.basicConfig(level=logging.DEBUG)

async def testUser(loop,**kw):
	await orm.create_pool(loop=loop, user='www-data', password='www-data', db='awesome')
	u = User(name=kw.get('name'), email=kw.get('email'), passwd=kw.get('passwd'), image=kw.get('image'))
	await u.save()
	await orm.close_pool()

userData=dict(name='gaf', email='235123345@qq.com', passwd='1312345', image='about:blank')
loop=asyncio.get_event_loop()
loop.run_until_complete(testUser(loop,**userData))
loop.close()
