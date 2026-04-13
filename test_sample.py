"""Sample file for testing PyBuddy analysis."""

import pandas as pd
import os
import requests
import json

# Anti-pattern: mutable default argument
def process_data(items=[]):
    results = []
    for item in items:
        results.append(item * 2)
    return results

# Anti-pattern: iterrows
def analyze_df(df):
    for index, row in df.iterrows():
        print(row['name'], row['value'])

# Anti-pattern: open without with
def read_file(path):
    f = open(path, 'r')
    data = f.read()
    f.close()
    return data

# Anti-pattern: bare except
def risky_operation():
    try:
        result = 1 / 0
    except:
        pass

# Anti-pattern: type comparison
def check_type(x):
    if type(x) == str:
        return True
    return False

# Good code using with
def read_json(path):
    with open(path) as f:
        return json.load(f)

# Using os.path instead of pathlib
def join_paths(a, b):
    return os.path.join(a, b)

# requests without timeout
def fetch_data(url):
    response = requests.get(url)
    return response.json()
