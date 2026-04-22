# -*- coding: utf-8 -*-
"""测试 chat 接口"""
import requests
import json

url = "http://localhost:8000/chat"
headers = {"Content-Type": "application/json"}

# 测试1: 简单问题
data1 = {"question": "你的名字是什么？"}
print("=== 测试 1: 简单问题 ===")
print(f"请求数据: {json.dumps(data1, ensure_ascii=False)}")
response1 = requests.post(url, json=data1, headers=headers)
print(f"响应状态码: {response1.status_code}")
print(f"响应内容: {json.dumps(response1.json(), ensure_ascii=False, indent=2)}")
print()

# 测试2: 关于文档内容的问题
data2 = {"question": "请介绍一下这个人"}
print("=== 测试 2: 关于文档内容的问题 ===")
print(f"请求数据: {json.dumps(data2, ensure_ascii=False)}")
response2 = requests.post(url, json=data2, headers=headers)
print(f"响应状态码: {response2.status_code}")
print(f"响应内容: {json.dumps(response2.json(), ensure_ascii=False, indent=2)}")
print()

# 测试3: 查询知识库状态
print("=== 测试 3: 查询知识库状态 ===")
url_status = "http://localhost:8000/knowledge/status"
response3 = requests.get(url_status)
print(f"响应: {json.dumps(response3.json(), ensure_ascii=False, indent=2)}")
