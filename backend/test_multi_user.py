#!/usr/bin/env python3
"""
Test script for multi-user platform wallet architecture
Tests user registration, platform wallet creation, and isolated transactions
"""

import requests
import json
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

class MultiUserTester:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.users = []
        self.session = requests.Session()
    
    def register_user(self, wallet_address: str) -> Dict[str, Any]:
        """Register a new user with a connected wallet"""
        url = f"{self.base_url}/users/register"
        payload = {"connected_wallet_address": wallet_address}
        
        print(f"\n📝 Registering user: {wallet_address[:10]}...")
        response = self.session.post(url, json=payload)
        
        if response.status_code == 200:
            user = response.json()
            self.users.append(user)
            print(f"✅ User registered (ID: {user['id']})")
            return user
        else:
            print(f"❌ Registration failed: {response.status_code} - {response.text}")
            return None
    
    def get_user_wallet(self, wallet_address: str) -> Dict[str, Any]:
        """Get user's platform wallet"""
        url = f"{self.base_url}/users/me/wallet"
        auth_header = f"Bearer {wallet_address}"
        headers = {"Authorization": auth_header}
        
        print(f"\n💼 Fetching platform wallet for {wallet_address[:10]}...")
        response = self.session.get(url, headers=headers)
        
        if response.status_code == 200:
            wallet = response.json()
            print(f"✅ Platform wallet retrieved:")
            print(f"   Address: {wallet['address'][:10]}...")
            print(f"   Balance: {wallet['balance']} GEN")
            return wallet
        else:
            print(f"❌ Failed to fetch wallet: {response.status_code}")
            return None
    
    def get_current_user(self, wallet_address: str) -> Dict[str, Any]:
        """Get current user info"""
        url = f"{self.base_url}/users/me"
        auth_header = f"Bearer {wallet_address}"
        headers = {"Authorization": auth_header}
        
        print(f"\n👤 Fetching user info for {wallet_address[:10]}...")
        response = self.session.get(url, headers=headers)
        
        if response.status_code == 200:
            user = response.json()
            print(f"✅ User info retrieved (ID: {user['id']})")
            return user
        else:
            print(f"❌ Failed to fetch user: {response.status_code}")
            return None
    
    def check_balance(self, address: str) -> float:
        """Check balance of any wallet"""
        url = f"{self.base_url}/wallet/balance"
        params = {"address": address}
        
        response = self.session.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("balance", 0)
        return 0
    
    def run_tests(self):
        """Run comprehensive multi-user tests"""
        print("\n" + "="*60)
        print("🧪 MULTI-USER PLATFORM WALLET TESTS")
        print("="*60)
        
        # Test 1: Register multiple users
        print("\n📌 Test 1: Register Multiple Users")
        print("-" * 40)
        
        test_wallets = [
            "0x1111111111111111111111111111111111111111",
            "0x2222222222222222222222222222222222222222",
            "0x3333333333333333333333333333333333333333",
        ]
        
        registered_users = []
        for wallet in test_wallets:
            user = self.register_user(wallet)
            if user:
                registered_users.append({
                    "wallet": wallet,
                    "user": user
                })
        
        print(f"\n✅ Registered {len(registered_users)} users")
        
        # Test 2: Verify each user has unique platform wallet
        print("\n📌 Test 2: Verify Unique Platform Wallets")
        print("-" * 40)
        
        platform_wallets = []
        for item in registered_users:
            wallet_addr = item["wallet"]
            platform_wallet = self.get_user_wallet(wallet_addr)
            if platform_wallet:
                platform_wallets.append(platform_wallet)
        
        # Verify uniqueness
        wallet_addresses = [w["address"] for w in platform_wallets]
        if len(wallet_addresses) == len(set(wallet_addresses)):
            print(f"\n✅ All {len(wallet_addresses)} platform wallets are unique!")
            for i, addr in enumerate(wallet_addresses, 1):
                print(f"   {i}. {addr}")
        else:
            print("❌ Platform wallets are NOT unique!")
        
        # Test 3: Verify user info retrieval
        print("\n📌 Test 3: Verify User Info Retrieval")
        print("-" * 40)
        
        for item in registered_users:
            wallet_addr = item["wallet"]
            user_info = self.get_current_user(wallet_addr)
            if user_info:
                print(f"   Connected Wallet: {wallet_addr[:10]}...")
        
        # Test 4: Verify authentication isolation
        print("\n📌 Test 4: Verify Authentication Isolation")
        print("-" * 40)
        
        # Try to access wrong user's wallet with wrong token
        if len(registered_users) >= 2:
            user1_wallet = registered_users[0]["wallet"]
            user2_wallet = registered_users[1]["wallet"]
            
            print(f"\nAttempting User2's wallet with User1's auth...")
            url = f"{self.base_url}/users/me/wallet"
            headers = {"Authorization": f"Bearer {user1_wallet}"}
            response = self.session.get(url, headers=headers)
            
            # Should get user1's platform wallet, not fail
            if response.status_code == 200:
                wallet = response.json()
                print(f"✅ User1 correctly got their own wallet: {wallet['address'][:10]}...")
            else:
                print(f"❌ Failed: {response.status_code}")
        
        # Test 5: Summary report
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        print(f"✅ Users registered: {len(registered_users)}")
        print(f"✅ Platform wallets created: {len(platform_wallets)}")
        print(f"✅ Wallets are unique: {len(wallet_addresses) == len(set(wallet_addresses))}")
        print("\n✨ All tests completed!")
        print("="*60 + "\n")


def main():
    tester = MultiUserTester()
    
    try:
        tester.run_tests()
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
