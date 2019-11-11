#!/usr/bin/env python3
"""
Class to handle mysql databases
"""

from orderedattrdict import AttrDict

import pymysql
import pymysql.cursors
import requests


class Database:
    """
    Handle database connections
    
    Keep the connection open, and if any error try to reconnect
    before returning any errors
    """
    def __init__(self, db_conf):
        self.db_conf = db_conf
        self.conn = None
        self.cursor = None
        
    def connect(self):
        if self.conn is None:
            self.conn = pymysql.connect(
                    host=self.db_conf['host'], 
                    user=self.db_conf['user'], 
                    passwd=self.db_conf['pass'],
                    db=self.db_conf['name'],
                    cursorclass=pymysql.cursors.DictCursor)
        if self.cursor is None:
            self.cursor = self.conn.cursor()
        return self.conn
    
    def disconnect(self):
        self.close_cursor()
        if self.conn:
            self.conn.close()
        self.conn = None
    
    def close_cursor(self):
        if self.cursor:
            self.cursor.close()
        self.cursor = None
    
    def begin(self):
        for i in range(0, 2):
            self.connect()
            try:
                self.conn.begin()
                return
            except pymysql.MySQLError as e:
                if i == 1:
                    raise 
            self.disconnect()
        
    def commit(self):
        """
        We don't retry commit, if the connection is gone there are
        no transaction to commit
        """
        self.conn.commit()
        self.close_cursor()
    
    def rollback(self):
        """
        We don't retry rollback, if the connection is gone there are
        no transaction to rollback
        """
        self.conn.rollback()

    def _execute(self, sql, values=None):
        """
        Execute a query,
        if error try to reconnect and redo the query to handle timeouts
        """
        for i in range(0, 2):
            self.connect()
            try:
                if values is not None:
                    self.cursor.execute(sql, values)
                else:
                    self.cursor.execute(sql)
                return
            except pymysql.MySQLError as e:
                if i == 1:
                    raise
                self.disconnect()
    
    def last_insert_id(self):
        """
        Return last insert id, or None if not found
        """
        key = "LAST_INSERT_ID()"
        self._execute("SELECT " + key)
        row = self.cursor.fetchone()
        if key in row:
            return row[key]
        return None
    
    def row_count(self):
        """
        """
        key = "ROW_COUNT()"
        rows = self._execute(key)
        if len(rows):
            row = rows[0]
            if key in row:
                return row[key]
        return None

    def insert(self, table=None, d=None, primary_key=None, exclude=[], commit=True):
        """
        Insert a row in a table, using table name and a dict
        Primary is the key, which should be updated with last_inserted_id
        exclude are columns that should be ignored
        """
        if primary_key:
            exclude.append(primary_key)  # we always exclude the primary_key
        columns = []
        values = []
        for colname in d.keys() - exclude:
            columns.append(colname)
            values.append(d[colname])
        sql = "INSERT into %s (%s) VALUES (%s)" %\
            (table, ",".join(columns), ",".join(["%s"] * len(values) ) )
        self._execute(sql, values)
        id_ = self.last_insert_id()
        d[primary_key] = id_
        if commit:
            self.commit()
        return id_

    def update(self, table=None, d=None, primary_key=None, exclude=[], commit=True):
        """
        Update a row in a table, using table name and a dict
        exclude are columns that should be ignored
        """
        if primary_key:
            exclude.append(primary_key)  # we always exclude the primary_key
        columns = []
        values = []
        for colname in d.keys() - exclude:
            columns.append("`%s`" % colname)
            values.append(d[colname])
        sql = "UPDATE %s SET %s" %\
            (table, ",".join("{!s}=%s".format(colname) for colname in columns))
        sql += " WHERE %s=%%s" % primary_key
        values.append(d[primary_key])
        self._execute(sql, values)

        if commit:
            self.commit()

    def delete(self, sql=None, values=None, commit=True):
        """
        Delete a row in a table, using table name and a dict
        """
        self._execute(sql, values)
        rowcount = self.cursor.rowcount
        if commit:
            self.commit()
        return rowcount
        
    def select_one(self, sql=None, values=None, commit=True):
        """
        Select one row from a table
        Returns an AttrDict(), or None if not found
        """
        self._execute(sql, values)
        row = self.cursor.fetchone()
        if commit:
            self.commit()
        if row:
            row = AttrDict(row)
        return row

    def select_all(self, sql=None, values=None, commit=True):
        """
        Select all rows from a table
        Returns a list of AttrDict()
        """
        self._execute(sql, values)
        rows = self.cursor.fetchall()
        if commit:
            self.commit()
        for ix in range(0, len(rows)):
            rows[ix] = AttrDict(rows[ix])
        return rows
