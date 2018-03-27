#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging; logging.basicConfig(level=logging.DEBUG)
import asyncio, os, inspect, functools
from urllib import parse
from aiohttp import web
from apis import APIError

def Handler_decorator(path, *, method):
	''' define decorator @get('/path') '''
	def decorator(func):
		@functools.wraps(func)
		def wrapper(*args, **kw):
			return func(*args, **kw)
		wrapper.__method__ = method
		wrapper.__route__ = path
		return wrapper
	return decorator

get = functools.partial(Handler_decorator, method = 'GET')
post = functools.partial(Handler_decorator, method = 'POST')

# 使用inspect模块，检查视图函数的参数  
  
# inspect.Parameter.kind 类型：  
# POSITIONAL_ONLY          位置参数  
# KEYWORD_ONLY             命名关键词参数  
# VAR_POSITIONAL           可选参数 *args  
# VAR_KEYWORD              关键词参数 **kw  
# POSITIONAL_OR_KEYWORD    位置或必选参数  
def get_required_kw_args(fn):
	args = []
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
			args.append(name)
	return tuple(args)

def get_named_kw_args(fn):
	args = []
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY:
			args.append(name)
	return tuple(args)

def has_named_kw_args(fn):
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY:
			return True

def has_var_kw_arg(fn):
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.VAR_KEYWORD:
			return True

def has_request_arg(fn):
	sig = inspect.signature(fn)
	params = sig.parameters
	found = False
	for name, param in params.items():
		if name == 'request':
			found = True
			continue
		if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
			raise ValueError('request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
	return found

class RequestHandler(object):
	"""docstring for RequestHandler"""
	# 先构造fn进入
	def __init__(self, app, fn):
		super(RequestHandler, self).__init__()
		logging.info('RequestHandler __init__: %s ' % fn.__route__)
		self._app = app
		self._func = fn
		self._has_request_arg = has_request_arg(fn)
		self._has_var_kw_arg = has_var_kw_arg(fn)
		self._has_named_kw_args = has_named_kw_args(fn)
		self._named_kw_args = get_named_kw_args(fn)
		self._required_kw_args = get_required_kw_args(fn)

	# 用预定的fn处理传入的request，注意方法名定义为小写
	async def __call__(self, request):
		logging.info('RequestHandler __call__ route: %s ' % self._func.__route__)
		kw = None

		# 若视图函数有命名关键词或关键词参数 
		if self._has_request_arg or self._has_named_kw_args or self._has_var_kw_arg:
			if request.method == 'POST':
				# json() body , post() form表单
				if not request.content_type:
					return web.HTTPBadRequest('Missing content_type.')
				ct = request.content_type.lower()
				if ct.startswith('application/json'):
					params = await request.json
					if not isinstance(params, dict):
						return web.HTTPBadRequest('Json body must be object.')
					kw = params
				elif ct.startswith('applictaion/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
					params = await request.post()
					kw = dict(**params)
				else:
					return web.HTTPBadRequest('Unsupported content_type: %s ' % request.content_type)
			
			if request.method == 'GET': 
				# 返回URL查询语句，?后的键值。string形式。
				qs = request.query_string # 返回URL查询语句，?后的键值。string形式。  
				if qs:  
					kw = dict()  
                    # '''''
                    # 解析url中?后面的键值对的内容 
                    # qs = 'first=f,s&second=s' 
                    # parse.parse_qs(qs, True).items() 
                    # >>> dict([('first', ['f,s']), ('second', ['s'])]) 
                    # '''
					for k, v in parse.parse_qs(qs, True).items():
						# 返回查询变量和值的映射，True表示不忽略空格。
						kw[k] = v[0] 

		# 整理kw参数和request.match_info路径参数
		if kw is None:  # 若request中无参数  
			# 若存在可变路由：/a/{name}/c，可匹配path为：/a/jack/c的request 
			# {variable}为参数名，传入request请求的path为值 
			kw = dict(**request.match_info)
		else:	# request有参数
			if self._has_named_kw_args and (not self._has_var_kw_arg):
				# 只有命名参数，没有关键字参数，需要只保留命名参数即可
				copy = dict()
				for name in self._named_kw_args:
					if name in kw:
						copy[name] = kw[name]
				kw = copy

			# 将request.match_info中的参数传入kw，但要覆盖kw中已有关键字参数
			for k, v in request.match_info.items():
				if k in kw:
					logging.warn('Duplicat arg name in named arg and kw args: %s ' % k)
				kw[k] = v

		# 整理request参数
		if self._has_request_arg:
			kw['request'] = request

		# 整理视图函数中存在无默认值的命名参数，检查是否已传入kw
		if self._required_kw_args:
			for name in self._required_kw_args:
				if not name in kw:
					return web.HTTPBadRequest('Missing argument: %s ' % name)

		# 至此，kw为request带入给视图函数fn真正可调用的全部参数
		logging.info('call with args: %s ' % str(kw))

		try:
			r = await self._func(**kw)
			return r
		except APIError as e:
			logging.error('Exception: %s' % e)
			return dict(error=e.error, data=e.data, message=e.message)

# 添加静态文件，如image，css，javascript等
def add_static(app):
	# 拼接static文件目录
	path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
	# path = os.path.join(os.path.abspath('.'), 'static')

	app.router.add_static('/static/', path)
	logging.info('add static %s => %s' % ('/static/', path))

# 编写一个add_route函数，用来注册一个视图函数  
def add_route(app, fn): 
	method = getattr(fn, '__method__', None)
	path = getattr(fn, '__route__', None)
	if method is None or path is None:
		raise ValueError('@get or @post not defined in %s.' % fn.__name__)
	# 判断URL处理函数是否协程并且是生成器  
	if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
		fn = asyncio.coroutine(fn)
	logging.info('add route %s %s => %s(%s)' % (method, path, fn.__name__, ','.join(inspect.signature(fn).parameters.keys())))  
	app.router.add_route(method, path, RequestHandler(app, fn))


# 导入模块，批量注册视图函数
def add_routes(app, module_name):
	n = module_name.rfind('.') # 从右侧检索，返回索引。若无，返回-1。
	# 导入整个模块
	if n == -1:
		# __import__ 作用同import语句，但__import__是一个函数，并且只接收字符串作为参数
		# __import__('os',globals(),locals(),['path','pip'], 0) ,等价于from os import path, pip
		mod = __import__(module_name, globals(), locals())
	else:
		name = module_name[(n+1):]
		# 导入所有的name模块的属性，为后续调用dir()
		mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
	for attr in dir(mod): # dir()迭代出mod模块中所有的类，实例及函数等对象,str形式
		if attr.startswith('_'):
			continue # 忽略'_'开头的对象，直接继续for循环
		fn = getattr(mod, attr)
		# 确保是函数
		if callable(fn):
			# 确保视图函数存在method和path
			method = getattr(fn, '__method__', None)
			path = getattr(fn, '__route__', None)
			if method and path:
				# 注册
				add_route(app, fn)