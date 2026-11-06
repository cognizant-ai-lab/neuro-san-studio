#!/usr/bin/env python3
# Copyright © 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# END COPYRIGHT

"""Test basic ServiceNow instance accessibility"""

import sys

import requests

INSTANCE_URL = "https://appoxiotechnologiesincdemo3.service-now.com/"

print(f"Testing ServiceNow instance: {INSTANCE_URL}")
print("=" * 50)

# Test 1: Basic instance accessibility
print("1. Testing basic instance accessibility...")
try:
    response = requests.get(INSTANCE_URL, timeout=10)
    print(f"   Status: {response.status_code}")
    print("   Instance is accessible")
except requests.RequestException as e:
    print(f"   ERROR: {e}")
    sys.exit(1)

# Test 2: Test login page
print("\n2. Testing login page...")
try:
    LOGIN_URL = f"{INSTANCE_URL}login.do"
    response = requests.get(LOGIN_URL, timeout=10)
    print(f"   Login page status: {response.status_code}")
    if "ServiceNow" in response.text:
        print("   Confirmed ServiceNow instance")
    else:
        print("   Warning: May not be a ServiceNow instance")
except requests.RequestException as e:
    print(f"   ERROR: {e}")

# Test 3: Test API endpoint accessibility (without auth)
print("\n3. Testing API endpoint accessibility...")
try:
    API_URL = f"{INSTANCE_URL}api/now/table/sys_user?sysparm_limit=1"
    response = requests.get(API_URL, timeout=10)
    print(f"   API endpoint status: {response.status_code}")
    if response.status_code == 401:
        print("   Good: API requires authentication (expected)")
    elif response.status_code == 200:
        print("   Warning: API accessible without auth (unexpected)")
    else:
        print(f"   API response: {response.text[:200]}")
except requests.RequestException as e:
    print(f"   ERROR: {e}")

print("\nInstance accessibility test completed.")
print("If authentication is still failing, the credentials may be incorrect")
print("or the instance may require different auth methods (OAuth, MFA, etc.)")
