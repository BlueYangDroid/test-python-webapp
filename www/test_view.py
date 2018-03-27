#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging; logging.basicConfig(level=logging.DEBUG)
from coroweb import get
import asyncio
from aiohttp import web

@get('/')
async def index(request):
	logging.info('index(request) ...')
	# resp = web.Response(body=u'<h1>Test index</h1>'.encode('utf-8'))
	# resp.content_type = 'text/html;charset=utf-8'
	# return resp

	user1=dict(name='user1', email='user1@qq.com', passwd='user1pw', image='about:blank')
	user2=dict(name='user2', email='user2@qq.com', passwd='user2pw', image='about:blank')
	users = [user1, user2]
	return {
		'__template__': 'test.html',
		'users': users
	}

@get('/hello/{name}')
async def hello(name, request):
	logging.info('hello(request) ... %s ' % name)
	return '<h1>hello %s!</h1>' % name