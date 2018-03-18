# test-python-webapp
test python web libs 2018

mysql兼容性问题：
1.本文所用到的mysql数据库可以去官网下载，但是该数据库只支持python3.4版本，若要通过python连接数据库，需要下载pymysql模块。
2.本文需要使用到异步aiomysql模块，该模块可能与pymysql模块存在版本不兼容问题。妥善处理方式是，更新aiomysql版本为0.0.7，pymysql版本为0.6.7

mysql脚本执行：
下列命令即可在mysql数据库中创建相应的数据表：
1，mysql -u root -q进入mysql环境
2，source F:\<脚本文件路径>\shemal.sql
