#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
async web application.
'''
import logging; logging.basicConfig(level=logging.DEBUG)
import asyncio, os, json, time
from datetime import datetime
from aiohttp import web
from jinja2 import Environment, FileSystemLoader

import orm
from coroweb import add_routes, add_static


def init_jinja2(app, **kw):
	logging.info('init jinja2...')
	    # 配置options参数  
	options = dict(  
        # 自动转义xml/html的特殊字符  
		autoescape = kw.get('autoescape', True),  
        # 代码块的开始、结束标志  
		block_start_string = kw.get('block_start_string', '{%'),  
		block_end_string = kw.get('block_end_string', '%}'),  
        # 变量的开始、结束标志  
		variable_start_string = kw.get('variable_start_string', '{{'),  
		variable_end_string = kw.get('variable_end_string', '}}'),  
        # 自动加载修改后的模板文件  
		auto_reload = kw.get('auto_reload', True)  
    )      # 配置options参数  

	# 获取模板文件夹路径 
	path = kw.get('path', None)
	if not path:
		# os.path.abspath(__file__)获取当前运行脚本的绝对路径
		path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')

	env = Environment(loader = FileSystemLoader(path), **options)
	
	# filters是Environment类的属性：过滤器处理字典
	filters = kw.get('filters', None)
	if filters:
		for name, f in filters.items():
			env.filters[name] = f

	# 所有的模板和过滤器都给app全局保存
	app['__template__'] = env


# 编写用于输出日志的middleware
# app, handler 由中间件框架传入:
# 	handler是封装处理具体path视图函数的RequestHandler函数体
# request是aiohttp传给path视图函数的RequestHandler的请求体
async def logger_factory(app, handler):
	async def logger(request):
		logging.info('logger_factory handler: %s %s' % (request.method, request.path))
		return await handler(request)
	return logger

# 处理视图函数返回值，制作response的middleware，构造出真正的web.Response对象 
async def response_factory(app, handler):
	async def response(request):
		logging.info('response_factory handler...')
		# RequestHandler处理之后的切面
		r = await handler(request)
		logging.info('response result = %s' % str(r))
		if isinstance(r, web.StreamResponse):
			# StreamResponse是所有WebResponse的父类
			return r
		if isinstance(r, bytes):
			resp = web.Response(body=r)
			resp.content_type = 'application/octet-stream'
			return resp
		if isinstance(r, str):
			if r.startswith('redirect:'): # 若返回重定向字符串 :
				return web.HTTPFound(r[9:]) # 重定向至目标URL  
			resp = web.Response(body=r.encode('utf-8'))
			resp.content_type = 'text/html;charset=utf-8' # utf-8编码的text格式  
			return resp

		# r为dict对象时，调用内嵌的template路径
		if isinstance(r, dict):
			# 在后续构造视图函数返回值时，会加入__template__值，用以选择渲染的模板 
			template = r.get('__template__', None)
			if template is None: # 不带模板信息，返回json对象
				# ensure_ascii：默认True，仅能输出ascii格式数据。故设置为False。  
				# default：r对象会先被传入default中的函数进行处理，然后才被序列化为json对象  
				# __dict__：以dict形式返回对象属性和值的映射  
				resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda obj: obj.__dict__).encode('utf-8'))
				resp.content_type = 'application/json;charset=utf-8'
				return resp
			else: # 带模板信息，渲染模板
				# 调用Template对象的render()方法，传入r渲染模板，返回unicode格式字符串，将其用utf-8编码
				resp = web.Response(body=app['__template__'].get_template(template).render(**r))
				resp.content_type = 'text/html;charset=utf-8'
				return resp

		# 返回响应码
		if isinstance(r, int) and (600>r>=100): 
			resp = web.Response(status=r)
			return resp

		# 返回了一组响应代码和原因，如：(200, 'OK'), (404, 'Not Found')
		if isinstance(r, tuple) and len(r) == 2:
			status_code, message = r
			if isinstance(status_code, int) and (600>status_code>=100):
				resp = web.Response(status=r, text=str(message))

		# 均以上条件不满足，默认返回
		resp = web.Response(body=str(r).encode('utf-8'))
		resp.content_type = 'text/plain;charset=utf-8'
		return resp
	return response

# 赋给jinja时间类处理过滤器
def datetime_filter(t):
	delta = int(time.time() - t)
	if delta < 60:
		return u'1分钟前'
	if delta < 3600:
		return u'%s分钟前' % (delta//60)
	if delta < 86400:
		return u'%s小时前' % (delta//3600)
	if delta < 604800:
		return u'%s天前' % (delta//86400)
	dt = datetime.fromtimestamp(t)
	return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)

if __name__ == '__main__':

	async def init(loop):
		app = web.Application(loop = loop, middlewares=[logger_factory, response_factory])

		init_jinja2(app, filters=dict(datetime = datetime_filter))
		add_routes(app, 'test_view')
		add_static(app)
		srv = await loop.create_server(app.make_handler(), 'localhost', 9000)
		logging.info('server started at http://127.0.0.1:9000...')
		return srv

	loop = asyncio.get_event_loop()
	loop.run_until_complete(init(loop))
	loop.run_forever()

# def index(request):
# 	return web.Response(body=b'<h1>Test python</h1>', content_type='text/html')

# async def init(loop):
# 	app = web.Application(loop=loop)	
# 	app.router.add_route('GET', '/', index)
# 	srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
# 	logging.info('server started at http://127.0.0.1:9000 ...')
# 	return srv

# loop = asyncio.get_event_loop()
# loop.run_until_complete(init(loop))
# loop.run_forever()