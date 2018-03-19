#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging; logging.basicConfig(level=logging.DEBUG)
import asyncio
import aiomysql

def log(sql, args=()):
	logging.info('SQL: %s' % sql)

async def create_pool(loop, **kw):
	logging.info('create database connect pool...')
	#生命pool为全局变量，aiomysql也用pool做协程
	global __pool
	__pool = await aiomysql.create_pool(
		host=kw.get('host', 'localhost'),
		port=kw.get('port', 3306),
		user=kw['user'],
		password=kw['password'],
		db=kw['db'],
		charset=kw.get('charset', 'utf8'),
		autocommit=kw.get('autocommit', True),
		maxsize=kw.get('maxsize', 10),
		minsize=kw.get('minsize', 1),
		loop=loop
		)
	logging.info('create database done')

async def close_pool():
	'''异步关闭连接池'''
	logging.info('close database connection pool...')
	global __pool
	__pool.close()
	await __pool.wait_closed()

# 查询方法, sql: 原始的？拼接
async def select(sql, args, size=None):
	log(sql, args)
	async with __pool.get() as conn:
		# 指定返回的cursor类型为aiomysql的DictCursor
		async with conn.cursor(aiomysql.DictCursor) as cur:
			# 调用和等待pool协程执行
			await cur.execute(sql.replace('?', '%s'), args or ())
			if size:
				rs = await cur.fetchmany(size)
			else:
				rs = await cur.fetchall()
		logging.info('rows returned: %s' % len(rs))

# 增改删方法
async def execute(sql, args, autocommit=True):
	log(sql, args)

	async with __pool.get() as conn:
		# 手动开启事务处理
		if not autocommit:
			await conn.begin()
		try:
			async with conn.cursor(aiomysql.DictCursor) as cur:
				await cur.execute(sql.replace('?', '%s'), args)
				affected = cur.rowcount
			# 手动提交事务
			if not autocommit:
				await conn.commit()
		except Exception as e:
			# 手动回滚事务
			if not autocommit:
				await conn.rollback()
			raise
		return affected

# n个？参数占位语句
def create_args_string(num):
	L = []
	for n in range(num):
		L.append('?')
	return ', '.join(L)


# orm中column -> Field构建
class Field(object):
	# 列名， 数据类型， 是否主键， 默认值
	def __init__(self, name, column_type, primary_key, default):
		self.name = name
		self.column_type = column_type
		self.primary_key = primary_key
		self.default = default

	def __str__(self):
		return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)

class StringField(Field):
			"""docstring for StringField"""
			def __init__(self, name=None, ddl='varchar(100)', primary_key=False, default=None):
				super(StringField, self).__init__(name, ddl, primary_key, default)

class BooleanField(Field):
	"""docstring for BooleanField"""
	def __init__(self, name=None, default=False):
		super(BooleanField, self).__init__(name, 'boolean', False, default)
		
class IntegerField(Field):

    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)

class FloatField(Field):

    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)

class TextField(Field):

    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)

# 元类，type
class ModelMetaclass(type):

    def __new__(cls, name, bases, attrs):
        #如果是基类对象,不做处理,因为没有字段名,没什么可处理的
        if name=='Model':
            return type.__new__(cls, name, bases, attrs)
        #保存表名,如果获取不到,则把类名当做表名,完美利用了or短路原理
        tableName = attrs.get('__table__', None) or name
        logging.info('found model: %s (table: %s)' % (name, tableName))
        #保存列类型的对象
        mappings = dict()
        #保存列名的数组
        fields = []
        #主键
        primaryKey = None
        for k, v in attrs.items():
            #是列名的就保存下来
            if isinstance(v, Field):
                logging.info('  found mapping: %s ==> %s' % (k, v))
                mappings[k] = v
                if v.primary_key:
                    # 找到主键:
                    if primaryKey:
                        raise StandardError('Duplicate primary key for field: %s' % k)
                    primaryKey = k
                else:
                    #保存非主键的列名
                    fields.append(k)
        if not primaryKey:
            raise StandardError('Primary key not found.')
        for k in mappings.keys():
            attrs.pop(k)
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))
        attrs['__mappings__'] = mappings # 保存属性和列的映射关系
        attrs['__table__'] = tableName
        attrs['__primary_key__'] = primaryKey # 主键属性名
        attrs['__fields__'] = fields # 除主键外的属性名
        #以下四种方法保存了默认了增删改查操作,其中添加的反引号``,是为了避免与sql关键字冲突的,否则sql语句会执行出错
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields), tableName)
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
        return type.__new__(cls, name, bases, attrs)


class Model(dict, metaclass=ModelMetaclass):
	"""docstring for Model"""
	def __init__(self, **kw):
		super(Model, self).__init__(**kw)

	def __getattr__(self, key):
		try:
			return self[key]
		except Exception as e:
			raise AttributeError(r"'Model' object has no attribute '%s'" % key)

	def __setattr__(self, key, value):
		self[key] = value

	def getValue(self, key):
		return getattr(self, key, None)

	def getValueOrDefault(self, key):
		# 先从dict中找，没有找到则从类定义时的field对象集中找默认值
		value = getattr(self, key, None)
		if value is None:
			field = self.__mappings__[key]
			if field.default is not None:
				value = field.default() if callable(field.default) else field.default
				logging.debug('useing defalt value for %s: %s' % (key, str(value)))
				setattr(self, key, value)
		return value
    
	@classmethod
	async def findAll(cls, where=None, args=None, **kw):
		sql = [cls.__select__]
		if where:
			sql.append('where')
			sql.append(where)
		if args is None:
			args = []

		orderBy = kw.get('orderBy', None)
		if orderBy:
			sql.append('order by')
			sql.append(orderBy)
		limit = kw.get('limit', None)
		if limit is not None:
			sql.append('limit')
			if isinstance(limit, int):
				sql.append('?')
				args.append(limit)
			elif isinstance(limit, tuple) and len(limit) == 2:
				sql.append('?, ?')
				args.extend(limit)
			else:
				raise ValueError('Invalid limit value: %s' % str(limit))
		rs = await select(' '.join(sql), args)
		all = [cls(**r) for r in rs]
		logging.info('findAll first: ', all[0])
		return all

	@classmethod
	async def findNumber(cls, selectField, where=None, args=None):
		' find number by select and where. '
		sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]
		if where:
			sql.append('where')
			sql.append(where)
			
		rs = await select(' '.join(sql), args, 1)
		if len(rs) == 0:
			return None
		return rs[0]['_num_']

	@classmethod
	async def find(cls, pk):
		' find object by primary key. '
		rs = await select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
		if len(rs) == 0:
			return None
		r = cls(**rs[0])
		logging.info('find: %s' % rows)
		return r

	async def save(self):
		args = list(map(self.getValueOrDefault, self.__fields__))
		args.append(self.getValueOrDefault(self.__primary_key__))
		rows = await execute(self.__insert__, args)
		if rows != 1:
			logging.warn('failed to insert record: affected rows: %s' % rows)
			
	async def update(self):
		args = list(map(self.getValue, self.__fields__))
		args.append(self.getValue(self.__primary_key__))
		rows = await execute(self.__update__, args)
		if rows != 1:
			logging.warn('failed to update by primary key: affected rows: %s' % rows)

	async def remove(self):
		args = [self.getValue(self.__primary_key__)]
		rows = await execute(self.__delete__, args)
		if rows != 1:
			logging.warn('failed to remove by primary key: affected rows: %s' % rows)
